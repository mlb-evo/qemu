"""Local persistent Driver Assist RTE inputs; no coding or BAP alteration."""
import sys
sys.dont_write_bytecode = True
from queue import Empty
import time

import gss_ipc_frames as ipc
from research.hmi.assist_catalog import SIGNALS


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
    if name == '@scenario' and field is None:
        from research.hmi.assist_scenarios import LABELS
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
        for name in SIGNALS if names is None else names:
            if name not in self.transmit and not force:
                continue
            value = pack(name, self.values[name])
            data_id = SIGNALS[name][0]
            stream += ipc.l4c_message(data_id, value + b'\0')
            if log:
                self.peer.log(f'tx RTE Assist {name} id={data_id:#05x} value={value.hex()} status=0')
        if stream:
            self.peer.queue(ipc.LUN_RTE, 0, stream)
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
        if name == '@scenario':
            from research.hmi.assist_scenarios import scenario
            profile = scenario(value)
            changed = self.transmit | set(profile)
            self.values = {key: dict(profile.get(key, {})) for key in SIGNALS}
            self.transmit = set(profile)
            self.peer.log(f'Assist scenario: {value}')
            self.send([key for key in SIGNALS if key in changed], log=True, force=True)
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
