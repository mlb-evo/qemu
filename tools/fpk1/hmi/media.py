"""Local Q7 0378 AudioSD BAP fixture (radio and media now playing).

GSS descriptors: FSG 0x31 at 0x1a85dc (BAP_Config bytes 03 00 31 00 04 04 at
0x1a8246), function table 0x19cf64; CAN CID 3 for short and CID 4 for long
properties, LUN 6. gtf2 handleDriverassistMedia (0x15779c) sets activation mask
bit 1 from ConfigM Driverassist_Media wire bit 5 ("BAP_AUDIO_ACTIVE").

Function IDs come from gtf2's AudioSD notify switch at 0x76fa1c (case = id - 1).
Status layouts come from gtf2's decoders (BapFcCodecTypes: MSB-first bits,
little-endian uint16, strings with a 1-byte length or, with bit 7 set, a
15-bit length):
  ActiveSource 0x10 (0x779780): SourceType u8, SourceList_Reference u16,
      TypeOfNumber u4, ListAvailable u4, List_State u4, Extension1 u4, Number u8
  ActiveSourceName 0x11 (0x779064): SourceName string
  Mute 0x13 (0x777934): MuteState u8
  SourceState 0x14 (0x77779c): StateInfo u8, StateInfo_Scope u8
  CurrentStationInfo 0x15 (0x778f50): Primary string, PI_Type u8, PI_ID u16,
      Secondary string, SI_Type u8, Tertiary string, TI_Type u8,
      Quaternary string, QI_Type u8, StationInfoSwitches u8,
      StationProperties u8, ASI u8, Channel_ID u16
  PlayPosition 0x34 (0x775d90): TimePosition u16, TotalPlayTime u16,
      Attributes u8, Extension u8
gtf2 0x1a4e74 treats SourceType 0..5, 0x0c, 0x11, 0x19, 0x1a, ... as tuner and
0x1a4ed0 treats 6..0x0b, 0x0d..0x10, 0x12..0x18, ... as media. Info type 0x49
is the artist and 0x4a the album (on_CurrentStationInfo_Status 0x19aac0).
Stock gtf2 scanout: 2 FM and 3 DAB show the station; 0x0f USB, 0x0b SD card,
0x10 player, 0x12 DVD and 0x14 CD show "Playback" with track, artist, album
and position; 0x0d is the external audio player (AUX).

ActiveSource ListAvailable bit 0 makes the stock gtf2 open the station list
view when the media tab is entered; its entries come over MOST (FBlock Audio
shadow, ReceptionList_PUSH), not BAP, so without an MMI on MOST it shows
"No entries are available." (layouts of BAP ReceptionList 0x17, which this
gtf2 decodes but never requests: au736_evo docs/firmware/gtf2-media-audiosd.md).
"""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
import time
from hmi.bap_availability import availability
from hmi.navigation import Navigation, function_list
from hmi.traffic_lights import TrafficReceiver, status_frames

FSG, LUN, MASK = 0x31, 6, 2
CONFIG_BIT, CONFIG_KEY = 5, 0x127
SHORT_CID, LONG_CID = 3, 4
# gss_ipc table: these functions use the long CID; all others the short one.
LONG = {0x01, 0x10, 0x11, 0x15, 0x17, 0x20, 0x21, 0x24, 0x2c, 0x32}
# GSS descriptor type 0xf (byte sequence): GetAll carries a uint16 length.
SEQUENCES = {0x11, 0x15}
RECEPTION_LIST_AVAILABLE = 1  # ActiveSource ListAvailable bit (stock scanout)
INFO = ('primary', 'secondary', 'tertiary', 'quaternary')
DEFAULT = dict(source_type=2, source_ref=1, number=0, list_state=0, source_name='FM',
               mute=0, state=0, primary='', primary_type=0, pi_id=0,
               secondary='', secondary_type=0, tertiary='', tertiary_type=0,
               quaternary='', quaternary_type=0, switches=0, properties=0, channel=0,
               position=0, total=0, playing=False, operation=0,
               list_available=0)
PRESETS = {
    'off': ('Аудио выключено', None),
    'radio_fm': ('Радио FM: станция и радиотекст', dict(
        DEFAULT, source_type=2, source_name='FM', primary='Radio 7', primary_type=1,
        secondary='Now: Morning show', secondary_type=2, pi_id=0xd3c2,
        list_available=RECEPTION_LIST_AVAILABLE)),
    'radio_dab': ('Радио DAB', dict(
        DEFAULT, source_type=3, source_name='DAB', primary='BBC Radio 2', primary_type=1,
        secondary='Pop Music', secondary_type=2, pi_id=0xc202,
        list_available=RECEPTION_LIST_AVAILABLE)),
    'media_usb': ('Медиа USB: трек играет', dict(
        DEFAULT, source_type=0x0f, source_name='USB', primary='Sunset Drive', primary_type=0x48,
        secondary='The Midnight Run', secondary_type=0x49, tertiary='Night Roads',
        tertiary_type=0x4a, position=42, total=245, playing=True)),
    'media_sd': ('Медиа SD-карта: трек играет', dict(
        DEFAULT, source_type=0x0b, source_name='SD', primary='Ocean Avenue', primary_type=0x48,
        secondary='Blue Harbour', secondary_type=0x49, tertiary='Coastline', tertiary_type=0x4a,
        position=0, total=198, playing=True)),
    'media_paused': ('Медиа USB: пауза', dict(
        DEFAULT, source_type=0x0f, source_name='USB', primary='Sunset Drive', primary_type=0x48,
        secondary='The Midnight Run', secondary_type=0x49, tertiary='Night Roads',
        tertiary_type=0x4a, position=42, total=245, state=1)),
    'media_aux': ('Внешний аудиоплеер (AUX)', dict(
        DEFAULT, source_type=0x0d, source_name='AUX')),
    'muted': ('Радио FM, звук выключен', dict(
        DEFAULT, source_type=2, source_name='FM', primary='Radio 7', primary_type=1, mute=1,
        list_available=RECEPTION_LIST_AVAILABLE)),
}


def preset(key):
    return deepcopy(PRESETS[key][1])


def valid_profile(value):
    if value is None:
        return True
    if not isinstance(value, dict) or value.keys() != DEFAULT.keys():
        return False
    for key, default in DEFAULT.items():
        data = value[key]
        if isinstance(default, bool):
            if type(data) is not bool:
                return False
        elif isinstance(default, str):
            if not isinstance(data, str) or len(data.encode()) > 127:
                return False
        else:
            hi = 0xffff if key in ('source_ref', 'pi_id', 'channel', 'position', 'total') else (
                15 if key in ('list_state', 'list_available') else 255)
            if type(data) is not int or not 0 <= data <= hi:
                return False
    return True


def text(value):
    data = value.encode()
    return bytes([len(data)]) + data


def properties(profile):
    p = profile
    info = b''.join(text(p[name]) + bytes([p[name + '_type']])
                    + (p['pi_id'].to_bytes(2, 'little') if name == 'primary' else b'')
                    for name in INFO)
    values = {
        2: bytes.fromhex('030031000404'),
        4: b'\0',
        0x0f: bytes([p['operation'], 0]),
        0x10: bytes([p['source_type']]) + p['source_ref'].to_bytes(2, 'little')
        + bytes([p['list_available'], p['list_state'] << 4, p['number']]),
        0x11: text(p['source_name']),
        0x13: bytes([p['mute']]),
        0x14: bytes([p['state'], 0]),
        0x15: info + bytes([p['switches'], p['properties'], 0]) + p['channel'].to_bytes(2, 'little'),
        0x34: p['position'].to_bytes(2, 'little') + p['total'].to_bytes(2, 'little') + b'\0\0',
    }
    values[3] = function_list((*values, 3))
    return dict(sorted(values.items()))


class Media:
    reassemble = Navigation.reassemble

    def __init__(self, peer):
        self.peer = peer
        self.profile = None
        self.segments = {}
        self.next_tick = 0.
        self.availability = availability(peer)
        peer.reassembler = TrafficReceiver(peer.reassembler, self)

    def select(self, profile):
        if not valid_profile(profile):
            raise ValueError('Invalid media profile')
        self.profile = deepcopy(profile)
        self.next_tick = time.monotonic() + 1
        self.availability.select('media', CONFIG_BIT, MASK, profile is not None, key=CONFIG_KEY)

    def reply(self, function, payload, opcode=4):
        cid = LONG_CID if function in LONG else SHORT_CID
        for frame in status_frames(function, payload, opcode, fsg=FSG):
            self.peer.queue(LUN, cid, frame)

    def get_all(self):
        return b''.join(len(value).to_bytes(2, 'little') + value if key in SEQUENCES else value
                        for key, value in properties(self.profile).items())

    def receive(self, lun, cid, data):
        if self.profile is None or lun != LUN or cid not in (SHORT_CID, LONG_CID) or len(data) < 2:
            return
        data = self.reassemble(cid, data)
        if data is None or len(data) < 2 or ((data[0] & 15) << 2 | data[1] >> 6) != FSG:
            return
        opcode, function, value = data[0] >> 4, data[1] & 63, data[2:]
        values = properties(self.profile)
        self.peer.log(f'rx BAP AudioSD opcode={opcode} function={function:#x} data={value.hex()}')
        if opcode == 1 and not value:
            if function == 1:
                self.reply(1, self.get_all(), opcode=3)
            elif function in values:
                self.reply(function, values[function])

    def send(self):
        if self.profile is None:
            return
        self.availability.send()
        values = properties(self.profile)
        for function in (0x0f, 0x10, 0x11, 0x13, 0x14, 0x15, 0x34):
            self.reply(function, values[function])
        self.peer.log(f'tx BAP AudioSD source={self.profile["source_type"]:#x} '
                      f'"{self.profile["primary"]}"')

    def tick(self):
        """Advance a playing track once a second (PlayPosition Status)."""
        p = self.profile
        if p is None or not p['playing'] or time.monotonic() < self.next_tick:
            return
        self.next_tick += 1
        p['position'] = p['position'] + 1 if p['position'] < p['total'] else 0
        self.reply(0x34, properties(p)[0x34])
