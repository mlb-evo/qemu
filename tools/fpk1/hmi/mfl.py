"""Local Q7 0378 steering-wheel input; original firmware remains unchanged.

gss_ipc l4c descriptor 0x1ae1e0: dataID 0x1cc, 4 bytes, callback
0x169700 -> unpacker 0x1656b0 -> Rte_Write(0x6e, 0).
gtf2 converter 0x18c82c, key index table 0x7da8a4, events 0x7da5a8.
"""
from collections import deque
from queue import Empty
import time

import gss_ipc_frames as ipc

DATA_ID = 0x1cc
# Event 1 maps to *_pressed; 2 is ignored by the button converter; 4 is long.
BUTTONS = {'left': 3, 'right': 2, 'view': 1, 'ok': 7, 'back': 8,
           'menu': 9, 'side_left': 10, 'side_right': 11}
ACTIONS = (*BUTTONS, 'up', 'down')


def signal(key1=0, event1=0, key2=0, event2=0, brand=0, variant=0):
    """Wire order differs from the four-byte in-memory RTE struct."""
    if not all(0 <= v <= 15 for v in (event1, event2, brand, variant)):
        raise ValueError('MFL event/identity fields must fit in a nibble')
    return bytes([event1 | event2 << 4, brand | variant << 4, key1, key2])


def pulse(action):
    """A click/one roller tick followed by release and neutral state.

    gtf2 suppresses identical consecutive key/event pairs (0x18bce8).
    Roller event 1 yields -1 tick; 15 yields +1 (0x18c8d8).
    """
    if action in BUTTONS:
        key = BUTTONS[action]
        return (signal(key, 1), signal(key, 2), signal())
    if action in ('up', 'down'):
        return (signal(6, 1 if action == 'up' else 15), signal())
    raise ValueError(f'Unknown wheel action: {action}')


class WheelInput:
    # ACK only confirms transport receipt; allow the guest RTE/DP tasks to run
    # before changing state, since rapid updates may otherwise be coalesced.
    SETTLE = 0.15

    def __init__(self, peer, commands):
        self.peer, self.commands = peer, commands
        self.pending = deque()
        self.inflight = None
        self.next_at = 0.0

    def delivered(self, frame):
        if self.inflight == frame:
            self.inflight = None
            self.next_at = time.monotonic() + self.SETTLE

    def tick(self):
        if self.inflight is not None or time.monotonic() < self.next_at:
            return
        if not self.pending:
            try:
                action = self.commands.get_nowait()
            except Empty:
                return
            if not self.peer.application_running:
                self.peer.log(f'wheel {action}: ignored, application run not acknowledged')
                return
            self.pending.extend(pulse(action))
            self.peer.log(f'wheel {action}: MFL pulse')
        payload = self.pending.popleft()
        self.peer.queue(*ipc.rte_signal(DATA_ID, payload))
        self.inflight = self.peer.outbox[-1]
        self.peer.log(f'tx RTE MFL_Tasten_Kon_01 id=0x1cc value={payload.hex()} status=0')
