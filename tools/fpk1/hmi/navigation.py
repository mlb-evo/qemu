"""Local Q7 0378 NavigationSD BAP fixture; all values are raw firmware codes.

GSS descriptors: FSG 0x32 at 0x1a8618 (BAP_Config bytes at 0x1a824c),
function table 0x19d61c; CAN CID 5 for short and CID 6 for long properties.
gtf2 handleDriverassistMedia (0x15779c) sets activation mask bit 2 from
ConfigM Driverassist_Media wire bit 14 (coding bit 87, "BAP_NAVIGATION_ACTIVE").
gtf2 logs NavSD FSG_OperationState (function 15) at 0x1793f4; 0 is normal.

Function IDs come from gtf2's NavSD notify switch at 0x78b250 (case = id - 1).
The side menu (Menu R) entries are DPs written by setMapDisplayAvailable
(0x1764f4) and setMapColorAndTypeAvailable (0x1765c8). They need
MapViewAndOrientation/MapColorAndType/MapScale in the FunctionList (0x179644)
and SupportedMapViews outside {0, 1, 2, 4} and SupportedMapTypes != 0.

CarPlay experiment (au736_evo patch carplay_map_display): a patched gtf2 adds
a fourth Map display item "CarPlay", shown while SupportedMapViews bit 3 is
set; it sends MapViewAndOrientation SetGet MapView 3 and sets Map_Presentation
(ASG_HMI_State) bit 1 while MapView 3 is requested. Stock gtf2 only reads
SupportedMapViews bits 0..2, so advertising bit 3 is harmless there.
"""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from hmi.bap_availability import availability
from hmi.traffic_lights import TrafficReceiver, status_frames

FSG, LUN, MASK = 0x32, 6, 4
CONFIG_BIT, CONFIG_KEY = 14, 0x127
# Function table CIDs: GetAll (1) uses the long CID; implemented properties CID 5.
SHORT_CID, LONG_CID = 5, 6
# Map settings: function -> initial Status bytes, in gtf2 log field order.
MAP = {
    0x11: bytes([0]),                       # RG_Status: no route guidance
    0x24: bytes([1]),                       # VoiceGuidance_State
    0x2b: bytes([0, 0, 0, 0x3f]),           # Colour, ActiveMapType, MainMapSetup, SupportedMapTypes
    0x2c: bytes([0, 0, 0xf, 0, 0, 0, 0]),   # MapView, Supplementary, SupportedMapViews,
                                            # SupportedSupplementary, MapVisibility, Orientation, Modification
    0x2d: bytes([0, 0, 0, 0, 0, 7]),        # Reserve, AutoZoom, AutoZoomState, Scale, Unit, SupportedAutoZoom
    0x36: bytes([0]),                       # Map_Presentation ASG_HMI_State
}
# MapView values (gtf2 sendMapDisplay table 0x7d1af4); 3 exists only with the
# CarPlay patch. ASG_HMI_State bit 0 is the cluster stage, bit 1 CarPlay.
MAP_VIEWS = {0: 'Standard', 1: 'Google Earth', 2: 'Traffic', 3: 'CarPlay'}
CARPLAY_VIEW, CARPLAY_BIT = 3, 2
# Bytes an HMI Set/SetGet may change; the others are Reserve in the request
# layout (e.g. MapViewAndOrientation SetGet zeroes SupportedMapViews) and
# MapScale's first request byte is a zoom step, not a stored value.
WRITABLE = {0x24: (0,), 0x2b: (0, 1, 2), 0x2c: (0, 1, 4, 5, 6), 0x2d: (1, 2), 0x36: (0,)}
# GSS descriptor type 0xf (byte sequence): GetAll carries a uint16 length.
SEQUENCES = {0x2c}
# map_views: SupportedMapViews; bit 3 shows the au736_evo CarPlay item.
DEFAULT = dict(operation=0, map_views=0x0f)
PRESETS = {
    'off': ('Навигация выключена', None),
    'normal': ('Навигация активна (OperationState 0)', DEFAULT),
    'no_carplay': ('Навигация активна, без CarPlay (SupportedMapViews 0x07)', dict(DEFAULT, map_views=0x07)),
}
for code in range(1, 16):
    PRESETS[f'operation_{code}'] = (f'OperationState = {code}', dict(DEFAULT, operation=code))


def preset(key):
    return deepcopy(PRESETS[key][1])


def valid_profile(value):
    if value is None:
        return True
    return (isinstance(value, dict) and value.keys() == DEFAULT.keys()
            and all(type(n) is int and 0 <= n <= 255 for n in value.values()))


def function_list(functions):
    bits = bytearray(8)
    for function in functions:
        bits[function // 8] |= 0x80 >> (function % 8)
    return bytes(bits)


def properties(profile, state=MAP):
    # FunctionList advertises exactly the implemented properties.
    values = {2: bytes.fromhex('030032000404'), 4: b'\0', 15: bytes([profile['operation']]), **state}
    values[3] = function_list((*values, 3))
    return dict(sorted(values.items()))


class Navigation:
    def __init__(self, peer):
        self.peer = peer
        self.profile = None
        self.state = dict(MAP)
        self.segments = {}
        self.carplay = None
        self.availability = availability(peer)
        peer.reassembler = TrafficReceiver(peer.reassembler, self)

    def select(self, profile):
        if not valid_profile(profile):
            raise ValueError('Invalid navigation profile')
        self.profile = deepcopy(profile)
        self.state = dict(MAP)
        if profile is not None:
            views = bytearray(self.state[0x2c])
            views[2] = profile['map_views']
            self.state[0x2c] = bytes(views)
            # Status for a running cluster; ignored before BAP_Config.
            self.reply(0x2c, self.state[0x2c])
        self.carplay = None
        self.availability.select('navigation', CONFIG_BIT, MASK, profile is not None, key=CONFIG_KEY)

    def reply(self, function, payload, opcode=4):
        cid = LONG_CID if function == 1 else SHORT_CID
        for frame in status_frames(function, payload, opcode, fsg=FSG):
            self.peer.queue(LUN, cid, frame)

    def get_all(self):
        return b''.join(len(value).to_bytes(2, 'little') + value if key in SEQUENCES else value
                        for key, value in properties(self.profile, self.state).items())

    def reassemble(self, cid, data):
        """Return a complete BAP request, collecting BAP's own segmentation."""
        if data[0] & 0xc0 == 0x80 and len(data) >= 4:
            self.segments[cid] = ((data[0] & 0x0f) << 8 | data[1], data[2:])
            data = b''
        elif data[0] & 0xc0 == 0xc0 and cid in self.segments:
            size, collected = self.segments[cid]
            self.segments[cid] = size, collected + data[1:]
            data = b''
        elif data[0] & 0x80:
            return None
        else:
            return data
        size, collected = self.segments[cid]
        if len(collected) < size + 2:
            return None
        del self.segments[cid]
        return collected[:size + 2]

    def receive(self, lun, cid, data):
        # Get (1) has no data; Set (0) and SetGet (2) carry new values for the
        # writable fields of one map property.
        if self.profile is None or lun != LUN or cid not in (SHORT_CID, LONG_CID) or len(data) < 2:
            return
        data = self.reassemble(cid, data)
        if data is None or len(data) < 2 or ((data[0] & 15) << 2 | data[1] >> 6) != FSG:
            return
        opcode, function, value = data[0] >> 4, data[1] & 63, data[2:]
        values = properties(self.profile, self.state)
        self.peer.log(f'rx BAP NavSD opcode={opcode} function={function:#x} data={value.hex()}')
        if opcode == 1 and not value:
            if function == 1:
                self.reply(1, self.get_all(), opcode=3)
            elif function in values:
                self.reply(function, values[function])
        elif opcode in (0, 2) and function in WRITABLE and 0 < len(value) <= len(self.state[function]):
            state = bytearray(self.state[function])
            for n in WRITABLE[function]:
                if n < len(value):
                    state[n] = value[n]
            self.state[function] = bytes(state)
            self.reply(function, self.state[function])
            if function == 0x2c:
                self.peer.log(f'tx BAP NavSD MapView={state[0]} ({MAP_VIEWS.get(state[0], "unknown")})')
            self.report_carplay()

    def report_carplay(self):
        # Logged on change only: gtf2 repeats Map_Presentation SetGet with
        # every FSG_OperationState Status.
        view = self.state[0x2c][0] == CARPLAY_VIEW
        presentation = bool(self.state[0x36][0] & CARPLAY_BIT)
        if (view, presentation) != self.carplay:
            self.carplay = view, presentation
            self.peer.log(f'tx BAP NavSD CarPlay {"selected" if view and presentation else "not selected"} '
                          f'(MapView={self.state[0x2c][0]}, Map_Presentation={self.state[0x36][0]:#04x})')

    def send(self):
        if self.profile is None:
            return
        self.availability.send()
        self.reply(15, properties(self.profile)[15])
        self.peer.log(f'tx BAP NavSD operation={self.profile["operation"]}')
