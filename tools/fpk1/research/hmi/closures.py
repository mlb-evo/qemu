"""Local Q7 0378 doors/bonnet/boot fixture on the original KSS RTE path.

gss_ipc descriptor 0x1abf30: dataID 0x10, length 2, callback 0x169bb0
-> unpacker 0x16728c -> Rte_Write(0x3c, 0). Trace formatter 0x13b73c
names bits 0..5: front left/right, rear left/right, boot, bonnet.
"""
import sys
sys.dont_write_bytecode = True
from queue import Empty
import time

import gss_ipc_frames as ipc

DATA_ID = 0x10
ACTIVE_ID = 0x1c2  # callback 0x16908c -> Rte_Write(0x3c, 1)
ZPM_INFO_ID = 0x272  # ten wire bytes; 0x167688 -> Rte_Write(0x46, 7)
CAR_OUTLINE_WARN_ID = 0xa800  # original gtf2 ZPM DB entry 0xa687f8
CLOSURES = (
    ('front_left', 'Front left', 0),
    ('front_right', 'Front right', 1),
    ('rear_left', 'Rear left', 2),
    ('rear_right', 'Rear right', 3),
    ('bonnet', 'Bonnet', 5),
    ('boot', 'Boot', 4),
)
BITS = {name: bit for name, _, bit in CLOSURES}


def signal(mask):
    if not 0 <= mask <= 0x3f:
        raise ValueError('Only the six supported closure bits may be set')
    # Rear window, spare wheel and fuel flap are kept closed; reserved = 0.
    return bytes([mask, 0])


def updates(mask, include_warning=True):
    # Local KSS fixture: request the outline while any supported opening is
    # open. gtf2 gates the four door display states on this separate signal.
    # Both updates share one l4c stream/SPI frame, so ACK covers both.
    warning = CAR_OUTLINE_WARN_ID if mask else 0
    # Flags, big-endian WarnID, PopupID, acoustic sync, sound/repeat/extra.
    zpm = b'\0' + warning.to_bytes(2, 'big') + bytes(7)
    return (ipc.l4c_message(DATA_ID, signal(mask) + b'\0') +
            ipc.l4c_message(ACTIVE_ID, bytes([bool(mask), 0])) +
            (ipc.l4c_message(ZPM_INFO_ID, zpm + b'\0') if include_warning else b''))


class Closures:
    SETTLE = .15

    def __init__(self, peer, commands=None):
        self.peer, self.commands = peer, commands
        self.mask = 0
        self.inflight = None
        self.next_at = 0.0

    def send(self, log=False):
        if self.inflight is not None:
            return
        payload = signal(self.mask)
        assist = getattr(self.peer, 'assist', None)
        include_warning = not (assist and assist.enabled('ZPM_HMI_Info'))
        self.peer.queue(ipc.LUN_RTE, 0, updates(self.mask, include_warning=include_warning))
        self.inflight = self.peer.outbox[-1]
        if log:
            self.peer.log(f'tx RTE CarOutline_HMI id=0x010 value={payload.hex()} status=0')
            self.peer.log(f'tx RTE CarOutline_HMI_Active id=0x1c2 value={int(bool(self.mask))} status=0')
            if include_warning:
                self.peer.log(f'tx RTE ZPM_HMI_Info id=0x272 WarnID={CAR_OUTLINE_WARN_ID if self.mask else 0:#06x} status=0')

    def delivered(self, frame):
        if self.inflight == frame:
            self.inflight = None
            self.next_at = time.monotonic() + self.SETTLE

    def tick(self):
        if self.commands is None or self.inflight is not None or time.monotonic() < self.next_at:
            return
        try:
            name, opened = self.commands.get_nowait()
        except Empty:
            return
        bit = 1 << BITS[name]
        self.mask = self.mask | bit if opened else self.mask & ~bit
        self.peer.log(f'closure {name}={"open" if opened else "closed"}')
        if self.peer.application_running:
            self.send(log=True)
