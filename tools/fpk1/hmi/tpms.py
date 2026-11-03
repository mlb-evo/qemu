"""Local Q7 0378 RDK BAP fixture; all values are raw firmware codes.

GSS descriptors: FSG 7 at 0x1a82d0, CAN CID 7 at 0x19aa04.
gtf2: coding mask bit 3 at 0x157670; readers 0x798bc0 (state),
0x79851c (pressure), 0x798334 (temperature), 0x79814c (required pressure).
State contains five pairs of pressure/temperature nibbles, then collected state.
"""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from hmi.bap_availability import availability
from hmi.traffic_lights import TrafficReceiver, status_frames

FSG, CAN_CID, MASK = 7, 7, 8
WHEELS = ('FL', 'FR', 'RL', 'RR')
# Guest scanout confirms unit 0: pressure = raw / 10 bar, temperature = raw - 60 °C.
DEFAULT = dict(pressure=[24, 24, 26, 26], temperature=[85, 85, 85, 85],
               required=[24, 24, 26, 26], state=[0, 0, 0, 0],
               temperature_state=[0, 0, 0, 0], collected=0,
               pressure_unit=0, temperature_unit=0, operation=0, lamp=0)
PRESETS = {
    'off': ('Stop TPMS transmission', None),
    'values_24_26': ('2.4 / 2.4 / 2.6 / 2.6 bar; 25 °C', DEFAULT),
    'values_20': ('2.0 bar on all wheels; 20 °C',
                  dict(DEFAULT, pressure=[20] * 4, temperature=[80] * 4)),
    'values_30': ('3.0 bar on all wheels; 40 °C',
                  dict(DEFAULT, pressure=[30] * 4, temperature=[100] * 4)),
    'lamp_off': ('RDK lamp = 0', dict(DEFAULT, lamp=0)),
    'lamp_on': ('RDK lamp = 1', dict(DEFAULT, lamp=1)),
}
for code in range(16):
    PRESETS[f'state_{code}'] = (f'Pressure state of all wheels = {code}',
                               dict(DEFAULT, state=[code] * 4))
for wheel, title in enumerate(('Front left', 'Front right', 'Rear left', 'Rear right')):
    values = deepcopy(DEFAULT)
    values['pressure'][wheel] = 16
    PRESETS[f'wheel_{WHEELS[wheel]}'] = (f'{title}: 1.6 bar, others 2.4 / 2.6 bar', values)


def preset(key):
    return deepcopy(PRESETS[key][1])


def valid_profile(value):
    if value is None:
        return True
    if not isinstance(value, dict) or value.keys() != DEFAULT.keys():
        return False
    for key, default in DEFAULT.items():
        data = value[key]
        hi = 15 if key in ('state', 'temperature_state') else (1 if key == 'lamp' else 255)
        if isinstance(default, list):
            if not isinstance(data, list) or len(data) != 4:
                return False
        else:
            data = [data]
        if not all(type(n) is int and 0 <= n <= hi for n in data):
            return False
    return True


def properties(profile):
    p = profile
    # FunctionList advertises exactly the implemented properties 2/3/15..19.
    state = bytes((a << 4) | b for a, b in zip(p['state'], p['temperature_state']))
    return {2: bytes.fromhex('030107000403'),
            3: bytes.fromhex('3801f00000000000'), 15: bytes([p['operation']]),
            16: state + bytes([0, p['collected']]),
            17: bytes([p['pressure_unit'], *p['pressure'], 255]),
            18: bytes([p['temperature_unit'], *p['temperature'], 255]),
            19: bytes([p['pressure_unit'], *p['required'], 255])}


class Tpms:
    def __init__(self, peer):
        self.peer = peer
        self.profile = None
        self.availability = availability(peer)
        peer.reassembler = TrafficReceiver(peer.reassembler, self)

    def select(self, profile):
        if not valid_profile(profile):
            raise ValueError('Invalid TPMS profile')
        self.profile = deepcopy(profile)
        self.availability.select('tpms', 5, MASK, profile is not None)

    def reply(self, function, payload, opcode=4):
        for frame in status_frames(function, payload, opcode, fsg=FSG):
            self.peer.queue(6, CAN_CID, frame)

    def get_all(self):
        values = properties(self.profile)
        return values[2] + values[3] + b'\0' + b''.join(values[key] for key in range(15, 20))

    def receive(self, lun, cid, data):
        if self.profile is None or (lun, cid) != (6, CAN_CID) or len(data) != 2:
            return
        if ((data[0] & 15) << 2 | data[1] >> 6) != FSG or data[0] >> 4 != 1:
            return
        function = data[1] & 63
        self.peer.log(f'rx BAP TPMS request function={function}')
        if function == 1:
            self.reply(1, self.get_all(), opcode=3)
        elif function in properties(self.profile):
            self.reply(function, properties(self.profile)[function])

    def send(self):
        if self.profile is None:
            return
        self.availability.send()
        for function, payload in properties(self.profile).items():
            if function >= 15:
                self.reply(function, payload)
        self.peer.log(f'tx BAP TPMS pressure={self.profile["pressure"]} temperature={self.profile["temperature"]}')
