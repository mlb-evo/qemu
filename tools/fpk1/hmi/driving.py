"""Local driving fixtures: vehicle speed, engine speed and gear over time.

Each preset is a repeating profile; while one is selected the peer sends its
values ten times a second on the original KSS RTE path, so the HMI's needles,
digits and the FAS road move with them. Wire formats (verified in au736_evo's
single-bit KSS runs, docs/firmware/hmikss-methods.md there):

- SPD_HMI_01, dataID 0x21: u16 big-endian, 0.01 km/h.
- TCH_HMI_EngineRPM, dataID 0x3: u16 big-endian (unit assumed 1/min).
- Gear_Display, dataID 0x23: 4 bytes; bits 31..28 engaged gear, 27..24
  selector (5 P, 6 R, 7 N, 8 D), bit 22 shows the selector, bit 20 the gear.
"""
import sys
sys.dont_write_bytecode = True
import math
import time

import gss_ipc_frames as ipc

SPEED_ID = 0x21
RPM_ID = 0x03
GEAR_ID = 0x23
PERIOD = 0.1
SELECTOR = {'P': 5, 'R': 6, 'N': 7, 'D': 8}


def ramp(t, points):
    """Piecewise linear over (time, value) points, repeating after the last."""
    t %= points[-1][0]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= t <= t1:
            # Ease in and out so the needles do not jerk at the corners.
            f = 0.5 - 0.5 * math.cos(math.pi * (t - t0) / (t1 - t0)) if t1 > t0 else 1
            return v0 + (v1 - v0) * f
    return points[-1][1]


def automatic(speed):
    """Engaged gear and engine speed of an eight-speed automatic in D."""
    if speed < 0.5:
        return 1, 750
    shifts = (0, 18, 32, 48, 65, 85, 105, 130)
    gear = sum(1 for s in shifts if speed >= s)
    low = shifts[gear - 1]
    high = shifts[gear] if gear < len(shifts) else 260
    return gear, int(1300 + 1500 * (speed - low) / (high - low))


def drive(points):
    def state(t):
        speed = ramp(t, points)
        gear, rpm = automatic(speed)
        return speed, rpm, 'D', gear
    return state


def reverse(t):
    speed = ramp(t, ((0, 0), (3, 0), (7, 8), (11, 8), (15, 0)))
    return speed, int(750 + 80 * speed), 'R', 0


PRESETS = {
    'park': ('Стоянка — P, 0 км/ч', lambda t: (0.0, 750, 'P', 0)),
    'city': ('Город — 0…50 км/ч, остановки', drive(((0, 0), (4, 0), (14, 50), (24, 50), (32, 0)))),
    'highway': ('Трасса — 100…130 км/ч', drive(((0, 100), (15, 130), (30, 130), (45, 100), (60, 100)))),
    'sprint': ('Разгон — 0…200 км/ч и торможение',
               drive(((0, 0), (3, 0), (28, 200), (33, 200), (45, 0)))),
    'reverse': ('Задний ход — R, до 8 км/ч', reverse),
}


def valid_profile(value):
    return value is None or (isinstance(value, str) and value in PRESETS)


def gear_signal(selector, gear):
    word = (gear & 0xf) << 28 | SELECTOR[selector] << 24 | 1 << 22 | (1 << 20 if gear else 0)
    return word.to_bytes(4, 'big')


def signals(speed, rpm, selector, gear):
    """(dataID, value) pairs of one sample."""
    return ((SPEED_ID, max(0, min(int(round(speed * 100)), 0xffff)).to_bytes(2, 'big')),
            (RPM_ID, max(0, min(int(rpm), 0xffff)).to_bytes(2, 'big')),
            (GEAR_ID, gear_signal(selector, gear)))


class Driving:
    def __init__(self, peer, clock=time.monotonic):
        self.peer, self.clock = peer, clock
        self.profile = None
        self.started = 0.0
        self.next_at = 0.0

    def select(self, key):
        """Starts preset key from its beginning; None stops sending."""
        self.profile = key
        self.started = self.next_at = self.clock()

    def sample(self):
        """(speed, rpm, selector, gear) now, or None while no preset runs."""
        if self.profile is None:
            return None
        return PRESETS[self.profile][1](self.clock() - self.started)

    def tick(self):
        if self.profile is None or not self.peer.application_running:
            return
        now = self.clock()
        if now < self.next_at:
            return
        self.next_at = now + PERIOD
        sample = PRESETS[self.profile][1](now - self.started)
        stream = b''.join(ipc.l4c_message(data_id, value + b'\0')
                          for data_id, value in signals(*sample))
        self.peer.queue(ipc.LUN_RTE, 0, stream)
