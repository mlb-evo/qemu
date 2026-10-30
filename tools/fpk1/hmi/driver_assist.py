"""Local persistent Driver Assist inputs, including the OnlineFunctions fixture."""
import sys
sys.dont_write_bytecode = True
from queue import Empty
import time

import gss_ipc_frames as ipc
from hmi.assist_catalog import SIGNALS


def limits(bits, signed=False):
    width = len(bits)
    return (-(1 << (width - 1)), (1 << (width - 1)) - 1) if signed else (0, (1 << width) - 1)


def pack(name, values):
    _, size, fields = SIGNALS[name]
    word = 0
    for field, bits, signed in fields:
        value = values.get(field, 0)
        lo, hi = limits(bits, signed)
        if not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(f'{name}.{field}: expected {lo}..{hi}')
        value &= (1 << len(bits)) - 1
        for n, bit in enumerate(bits):
            word |= ((value >> n) & 1) << bit
    return word.to_bytes(size, 'little')


def valid_command(name, field, value):
    if name == '@tpms' and field is None:
        from hmi.tpms import valid_profile
        return valid_profile(value)
    if name == '@scenario' and field is None:
        from hmi.assist_scenarios import LABELS
        return isinstance(value, str) and value in LABELS
    if name not in SIGNALS:
        return False
    if field is None:
        return isinstance(value, bool)
    for key, bits, signed in SIGNALS[name][2]:
        if key == field:
            lo, hi = limits(bits, signed)
            return isinstance(value, int) and lo <= value <= hi
    return False


class DriverAssist:
    SETTLE = .15

    def __init__(self, peer, commands):
        self.peer, self.commands = peer, commands
        self.values = {name: {} for name in SIGNALS}
        self.transmit = set()
        self.inflight = None
        self.next_at = 0.
        from hmi.traffic_lights import TrafficLights
        self.traffic = TrafficLights(peer)
        from hmi.tpms import Tpms
        self.tpms = Tpms(peer)

    def enabled(self, name):
        return name in self.transmit

    def delivered(self, frame):
        if frame == self.inflight:
            self.inflight = None
            self.next_at = time.monotonic() + self.SETTLE

    def send(self, names=None, log=False, force=False):
        if self.inflight is not None or not self.peer.application_running:
            return
        stream = bytearray()
        selected = list(SIGNALS if names is None else names)
        if self.tpms.profile is not None and 'TelltaleHMI_Display' not in selected:
            selected.append('TelltaleHMI_Display')
        for name in selected:
            tpms_lamp = name == 'TelltaleHMI_Display' and self.tpms.profile is not None
            if name not in self.transmit and not force and not tpms_lamp:
                continue
            values = dict(self.values[name])
            if tpms_lamp:
                values['tt_rdk_b'] = self.tpms.profile['lamp']
            value = pack(name, values)
            data_id = SIGNALS[name][0]
            stream += ipc.l4c_message(data_id, value + b'\0')
            if log:
                self.peer.log(f'tx RTE Assist {name} id={data_id:#05x} value={value.hex()} status=0')
        before = len(self.peer.outbox)
        if stream:
            self.peer.queue(ipc.LUN_RTE, 0, stream)
        self.traffic.send()
        self.tpms.send()
        if len(self.peer.outbox) > before:
            self.inflight = self.peer.outbox[-1]

    def tick(self):
        if self.inflight is not None or time.monotonic() < self.next_at:
            return
        try:
            name, field, value = self.commands.get_nowait()
        except Empty:
            return
        if not valid_command(name, field, value):
            self.peer.log('Assist: invalid command ignored')
            return
        if name == '@tpms':
            queued_before = len(self.peer.outbox)
            self.tpms.select(value)
            self.peer.log(f'TPMS profile: {value}')
            self.send(['TelltaleHMI_Display'], log=True, force=True)
            if self.inflight is None and len(self.peer.outbox) > queued_before:
                self.inflight = self.peer.outbox[-1]
            return
        if name == '@scenario':
            from hmi.assist_scenarios import scenario
            profile = scenario(value)
            queued_before = len(self.peer.outbox)
            self.traffic.select(value)
            changed = self.transmit | set(profile)
            self.values = {key: dict(profile.get(key, {})) for key in SIGNALS}
            self.transmit = set(profile)
            self.peer.log(f'Assist scenario: {value}')
            self.send([key for key in SIGNALS if key in changed], log=True, force=True)
            if self.inflight is None and len(self.peer.outbox) > queued_before:
                self.inflight = self.peer.outbox[-1]
            return
        if field is None:
            if value:
                self.transmit.add(name)
            else:
                self.transmit.discard(name)
            self.peer.log(f'Assist {name}: transmit={value}')
        else:
            self.values[name][field] = value
            self.peer.log(f'Assist {name}.{field}={value}')
        self.send([name], log=True)
