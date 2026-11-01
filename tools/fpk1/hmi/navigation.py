"""Local Q7 0378 NavigationSD BAP fixture; all values are raw firmware codes.

GSS descriptors: FSG 0x32 at 0x1a8618 (BAP_Config bytes at 0x1a824c),
function table 0x19d61c; CAN CID 5 for short and CID 6 for long properties.
gtf2 handleDriverassistMedia (0x15779c) sets activation mask bit 2 from
ConfigM Driverassist_Media wire bit 14 (coding bit 87, "BAP_NAVIGATION_ACTIVE").
gtf2 logs NavSD FSG_OperationState (function 15) at 0x1793f4; 0 is normal.
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
DEFAULT = dict(operation=0)
PRESETS = {
    'off': ('Навигация выключена', None),
    'normal': ('Навигация активна (OperationState 0)', DEFAULT),
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


def properties(profile):
    # FunctionList advertises exactly the implemented properties 2/3/4/15.
    return {2: bytes.fromhex('030032000404'), 3: bytes.fromhex('3801000000000000'),
            4: b'\0', 15: bytes([profile['operation']])}


class Navigation:
    def __init__(self, peer):
        self.peer = peer
        self.profile = None
        self.availability = availability(peer)
        peer.reassembler = TrafficReceiver(peer.reassembler, self)

    def select(self, profile):
        if not valid_profile(profile):
            raise ValueError('Invalid navigation profile')
        self.profile = deepcopy(profile)
        self.availability.select('navigation', CONFIG_BIT, MASK, profile is not None, key=CONFIG_KEY)

    def reply(self, function, payload, opcode=4):
        cid = LONG_CID if function == 1 else SHORT_CID
        for frame in status_frames(function, payload, opcode, fsg=FSG):
            self.peer.queue(LUN, cid, frame)

    def get_all(self):
        values = properties(self.profile)
        return b''.join(values[key] for key in sorted(values))

    def receive(self, lun, cid, data):
        if self.profile is None or lun != LUN or cid not in (SHORT_CID, LONG_CID) or len(data) != 2:
            return
        if ((data[0] & 15) << 2 | data[1] >> 6) != FSG or data[0] >> 4 != 1:
            return
        function = data[1] & 63
        self.peer.log(f'rx BAP NavSD request function={function}')
        if function == 1:
            self.reply(1, self.get_all(), opcode=3)
        elif function in properties(self.profile):
            self.reply(function, properties(self.profile)[function])

    def send(self):
        if self.profile is None:
            return
        self.availability.send()
        self.reply(15, properties(self.profile)[15])
        self.peer.log(f'tx BAP NavSD operation={self.profile["operation"]}')
