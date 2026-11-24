"""Local board computer fixture: trip data, consumption, range, odometer, clock.

While a profile is selected the peer sends these KSS RTE signals once a
second. Wire formats as au736_evo decodes them (docs/firmware/hmikss-methods.md
there); the units are assumed, not verified on a car:

- BC_HMI_ShortTerm 0x2, BC_HMI_LongTerm 0x1, BC_HMI_TankCycle 0x0
  (15 bytes, t_rte_BC_Level): byte 0 special, BC_distance u32 (0.1 km),
  BC_trip_time u32 (minutes), BC_average_cons u16 (0.1 l/100 km),
  BC_average_speed u16 (km/h) big-endian from byte 1, bytes 13..14 special.
- BC_HMI_Range 0x43 (28 bytes): byte 0 the unit (0 km), BC_total_range u32
  big-endian at bytes 1..4.
- BC_HMI_CurrentCons 0x125 (5 bytes): byte 0, then l/100 km and l/h as
  big-endian u16 (0.1).
- ODO_HMI_Distance 0x15 (9 bytes): byte 0 the error flags, total (km) and
  trip (0.1 km) as big-endian u32.
- CLK_HMI_dateTime 0x1e5 (8 bytes): year big-endian u16, second, minute,
  hour, day, month, isDST: the host's local time.

With `live` the counters follow the driving preset (hmi/driving.py): each
second adds the distance driven to the three trips and the odometer, takes it
from the range, and derives current and average consumption from the speed.
"""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
import time

import gss_ipc_frames as ipc

TANK_CYCLE_ID, LONG_TERM_ID, SHORT_TERM_ID = 0x0, 0x1, 0x2
RANGE_ID, CURRENT_CONS_ID, ODO_ID, CLOCK_ID = 0x43, 0x125, 0x15, 0x1e5
TRIPS = (('short', SHORT_TERM_ID), ('tank', TANK_CYCLE_ID), ('long', LONG_TERM_ID))
PERIOD = 1.0


def trip(distance, minutes, cons, speed):
    return {'distance': float(distance), 'minutes': int(minutes), 'cons': float(cons),
            'speed': int(speed)}


DEFAULT = dict(short=trip(0, 0, 0, 0), tank=trip(0, 0, 0, 0), long=trip(0, 0, 0, 0),
               range=0, current_cons=0.0, current_cons_h=0.0, odometer=0, trip=0.0, live=True)
PRESETS = {
    'city': ('Город: короткая поездка, высокий расход', dict(
        DEFAULT, short=trip(12.4, 38, 9.8, 19), tank=trip(312.6, 365, 8.1, 51),
        long=trip(8420.5, 9150, 7.6, 55), range=410, current_cons=11.2, current_cons_h=1.8,
        odometer=60382, trip=171.5)),
    'highway': ('Трасса: долгая поездка', dict(
        DEFAULT, short=trip(186.3, 102, 7.1, 110), tank=trip(540.2, 330, 7.0, 98),
        long=trip(23810.0, 19842, 7.3, 72), range=220, current_cons=6.4, current_cons_h=7.7,
        odometer=84120, trip=540.2)),
    'reserve': ('Резерв: бак почти пуст', dict(
        DEFAULT, short=trip(48.0, 51, 8.4, 56), tank=trip(812.7, 744, 7.9, 66),
        long=trip(15233.1, 14660, 7.8, 62), range=45, current_cons=8.9, current_cons_h=2.4,
        odometer=71540, trip=812.7)),
    'reset': ('Сброс: заправка, счётчики с нуля', dict(
        DEFAULT, short=trip(0, 0, 0, 0), tank=trip(0, 0, 0, 0), long=trip(0, 0, 0, 0),
        range=780, current_cons=0.0, current_cons_h=0.8, odometer=12, trip=0.0)),
}
LIMITS = dict(distance=(0, 0xffffffff / 10), minutes=(0, 0xffffffff), cons=(0, 0xffff / 10),
              speed=(0, 0xffff), range=(0, 0xffffffff), current_cons=(0, 0xffff / 10),
              current_cons_h=(0, 0xffff / 10), odometer=(0, 0xffffffff),
              trip=(0, 0xffffffff / 10))


def preset(key):
    return deepcopy(PRESETS[key][1])


def number(value, key):
    lo, hi = LIMITS[key]
    kind = int if key in ('minutes', 'speed', 'range', 'odometer') else (int, float)
    return isinstance(value, kind) and not isinstance(value, bool) and lo <= value <= hi


def valid_profile(value):
    if value is None:
        return True
    if not isinstance(value, dict) or value.keys() != DEFAULT.keys() or type(value['live']) is not bool:
        return False
    for name, _ in TRIPS:
        t = value[name]
        if not isinstance(t, dict) or t.keys() != DEFAULT[name].keys():
            return False
        if not all(number(t[key], key) for key in t):
            return False
    return all(number(value[key], key)
               for key in ('range', 'current_cons', 'current_cons_h', 'odometer', 'trip'))


def tenths(value):
    return int(round(value * 10))


def level_signal(t):
    return (b'\0' + tenths(t['distance']).to_bytes(4, 'big') + t['minutes'].to_bytes(4, 'big')
            + min(tenths(t['cons']), 0xffff).to_bytes(2, 'big')
            + min(t['speed'], 0xffff).to_bytes(2, 'big') + bytes(2))


def clock_signal(now):
    return (now.tm_year.to_bytes(2, 'big')
            + bytes([min(now.tm_sec, 59), now.tm_min, now.tm_hour, now.tm_mday, now.tm_mon,
                     1 if now.tm_isdst > 0 else 0]))


def signals(profile, now=None):
    """(dataID, value) pairs of one update; now: a time.struct_time for the clock."""
    p = profile
    result = [(data_id, level_signal(p[name])) for name, data_id in TRIPS]
    result += [
        (RANGE_ID, b'\0' + int(p['range']).to_bytes(4, 'big') + bytes(23)),
        (CURRENT_CONS_ID, b'\0' + min(tenths(p['current_cons']), 0xffff).to_bytes(2, 'big')
         + min(tenths(p['current_cons_h']), 0xffff).to_bytes(2, 'big')),
        (ODO_ID, b'\0' + int(p['odometer']).to_bytes(4, 'big')
         + tenths(p['trip']).to_bytes(4, 'big')),
        (CLOCK_ID, clock_signal(now or time.localtime())),
    ]
    return result


def fuel_per_hour(speed):
    """Assumed petrol consumption, l/h, of a large car at a steady speed."""
    return 0.8 + 0.035 * speed + 0.00025 * speed * speed


class BoardComputer:
    def __init__(self, peer, driving=None, clock=time.monotonic):
        self.peer, self.driving, self.clock = peer, driving, clock
        self.profile = None
        self.next_at = 0.0
        self.last = None
        self.fuel = {}
        self.seconds = {}
        self.odometer = 0.0
        self.range = 0.0

    def select(self, profile):
        if not valid_profile(profile):
            raise ValueError('Invalid board computer profile')
        self.profile = deepcopy(profile)
        self.last = self.next_at = self.clock()
        if profile is None:
            return
        # Fractions the integer wire fields cannot hold between updates.
        for name, _ in TRIPS:
            t = self.profile[name]
            self.fuel[name] = t['distance'] * t['cons'] / 100
            self.seconds[name] = t['minutes'] * 60.0
        self.odometer = float(self.profile['odometer'])
        self.range = float(self.profile['range'])

    def advance(self, dt):
        """Adds dt seconds of the driving preset's speed to the counters."""
        p = self.profile
        sample = self.driving.sample() if self.driving else None
        if not p['live'] or sample is None or dt <= 0:
            return
        speed = sample[0]
        moving = speed >= 1
        litres_h = fuel_per_hour(speed) if moving else 0.8
        p['current_cons_h'] = round(litres_h, 1)
        p['current_cons'] = round(min(litres_h / speed * 100, 99.9), 1) if moving else 0.0
        km = speed * dt / 3600
        for name, _ in TRIPS:
            t = p[name]
            t['distance'] += km
            self.seconds[name] += dt
            self.fuel[name] += litres_h * dt / 3600
            t['minutes'] = int(self.seconds[name] // 60)
            hours = self.seconds[name] / 3600
            t['speed'] = int(round(t['distance'] / hours)) if hours > 0 else 0
            t['cons'] = round(self.fuel[name] / t['distance'] * 100, 1) if t['distance'] >= 0.1 else 0.0
        self.odometer += km
        p['odometer'] = int(self.odometer)
        p['trip'] += km
        self.range = max(0.0, self.range - km)
        p['range'] = int(round(self.range))

    def tick(self):
        if self.profile is None or not self.peer.application_running:
            return
        now = self.clock()
        if now < self.next_at:
            return
        self.advance(now - self.last)
        self.last = now
        self.next_at = now + PERIOD
        stream = b''.join(ipc.l4c_message(data_id, value + b'\0')
                          for data_id, value in signals(self.profile))
        self.peer.queue(ipc.LUN_RTE, 0, stream)
