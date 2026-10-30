"""Local Q7 0378 OnlineFunctions display fixture, using original BAP transport.

GSS BapIpcService 0x1125b4: LUN 6, CAN CID 28, activation CID 17.
FSG 0x2a descriptors 0x1a85a0/0x19cdd4; version bytes at 0x1a8240.
The fixture temporarily enables only Config_BAP_Strecke bit 14 (coding bit
131). The original snapshot is restored when leaving a traffic scenario.
"""
import sys
sys.dont_write_bytecode = True

LUN, CAN_CID, MASK_CID = 6, 28, 17
FSG, ONLINE_MASK = 0x2a, 1 << 22
# Original gtf2 0x1d5314 maps wire 1 to green index 1, wire 3 to red index 2.
# Both colours were confirmed in captured QEMU scanout, not inferred from names.
PROFILES = {
    'traffic_red': (3, 20, 0),
    'traffic_green': (1, 0, 0),
    'traffic_countdown': (3, 8, 0),
    'traffic_speed': (1, 0, 50),
    'traffic_unavailable': (0, 0, 0),
}


def status_frames(function, data, opcode=4, *, fsg=FSG):
    """BAP CAN Status (opcode 4), including BAP's own segmentation."""
    header = bytes([(opcode << 4) | (fsg >> 2), ((fsg & 3) << 6) | function])
    if len(data) <= 6:
        return (header + data,)
    # Start frame length counts property data, excluding both BAP headers.
    frames = [bytes([0x80 | (len(data) >> 8), len(data) & 255]) + header + data[:4]]
    rest = data[4:]
    for n, offset in enumerate(range(0, len(rest), 7)):
        frames.append(bytes([0xc0 | (n & 15)]) + rest[offset:offset + 7])
    return tuple(frames)


class TrafficLights:
    def __init__(self, peer):
        self.peer = peer
        self.profile = None
        from hmi.bap_availability import availability
        self.availability = availability(peer)
        peer.reassembler = TrafficReceiver(peer.reassembler, self)

    def select(self, key):
        profile = PROFILES.get(key)
        if not profile and self.profile is not None:
            self.profile = (0, 0, 0)
            self.send()
        self.availability.select('traffic', 14, ONLINE_MASK, profile is not None)
        self.profile = profile

    def properties(self):
        signal, seconds, speed = self.profile
        return {2: bytes.fromhex('03002a000300'),
                3: bytes.fromhex('3801e00000000000'), 15: b'\0\0',
                16: bytes([signal, 0, 0, 0, 0, 0, 0, 0]),
                17: bytes([speed, 0, int(bool(speed))]),
                18: bytes([seconds, int(bool(seconds)), 0, 0, 0])}

    def get_all(self):
        # Original GSS 0x15ea34 consumes enabled properties in function order.
        # FunctionList has its legacy fixed 8-byte representation; variable
        # Info has a little-endian uint16 byte count. GetAll is not an empty ACK.
        values = self.properties()
        info = values[16]
        return (values[2] + values[3] + b'\0' + values[15]
                + len(info).to_bytes(2, 'little') + info + values[17] + values[18])

    def reply(self, function, payload, opcode=4):
        for frame in status_frames(function, payload, opcode):
            self.peer.queue(LUN, CAN_CID, frame)

    def receive(self, lun, cid, data):
        if self.profile is None or (lun, cid) != (LUN, CAN_CID) or len(data) != 2:
            return
        fsg = ((data[0] & 15) << 2) | (data[1] >> 6)
        opcode, function = (data[0] >> 4), data[1] & 63
        if fsg != FSG or opcode != 1:
            return
        self.peer.log(f'rx BAP OnlineFunctions request function={function}')
        if function == 1:
            # GetAll uses StatusAll (opcode 3), not property Status (4).
            self.reply(1, self.get_all(), opcode=3)
        elif function in self.properties():
            self.reply(function, self.properties()[function])

    def send(self):
        if self.profile is None:
            return
        self.availability.send()
        # Respond to initialization requests through TrafficReceiver; periodic
        # CAN display inputs do not restart BAP_Config/GetAll synchronization.
        values = self.properties()
        for function in (15, 16, 17, 18):
            self.reply(function, values[function])
        signal, seconds, speed = self.profile
        self.peer.log(f'tx BAP TrafficLightOnline signal={signal} time={seconds} speed={speed}')


class TrafficReceiver:
    """Observe completed BAP requests and retain KSS's normal receive path."""
    def __init__(self, decoder, traffic):
        self.decoder, self.traffic = decoder, traffic

    def feed(self, frame):
        messages = self.decoder.feed(frame)
        for message in messages:
            self.traffic.receive(*message)
        return messages
