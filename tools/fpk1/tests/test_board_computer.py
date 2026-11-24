"""Local board computer fixture: wire values, live counters, the peer and Qt."""
import sys
sys.dont_write_bytecode = True
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from queue import Queue
import time
import unittest

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import kss_peer
from hmi import board_computer as bc
from hmi.driver_assist import valid_command
from tests.test_tpms import rte_messages

NOON = time.struct_time((2026, 11, 23, 12, 34, 56, 0, 327, 0))


class Checks(unittest.TestCase):
    def test_wire_values(self):
        values = dict(bc.signals(bc.preset('city'), NOON))
        # 12.4 km, 38 min, 9.8 l/100 km, 19 km/h as au736_evo decodes t_rte_BC_Level.
        self.assertEqual(values[bc.SHORT_TERM_ID],
                         bytes.fromhex('00' '0000007c' '00000026' '0062' '0013' '0000'))
        self.assertEqual(len(values[bc.TANK_CYCLE_ID]), 15)
        self.assertEqual(values[bc.RANGE_ID], bytes.fromhex('00' '0000019a') + bytes(23))
        self.assertEqual(values[bc.CURRENT_CONS_ID], bytes.fromhex('00' '0070' '0012'))
        self.assertEqual(values[bc.ODO_ID], bytes.fromhex('00' '0000ebde' '000006b3'))
        self.assertEqual(values[bc.CLOCK_ID], bytes.fromhex('07ea' '38220c' '170b' '00'))

    def test_presets_valid(self):
        for key in bc.PRESETS:
            self.assertTrue(bc.valid_profile(bc.preset(key)), key)
        self.assertTrue(valid_command('@board', None, None))
        self.assertTrue(valid_command('@board', None, bc.preset('highway')))
        broken = bc.preset('city')
        broken['short']['speed'] = -1
        self.assertFalse(valid_command('@board', None, broken))
        self.assertFalse(valid_command('@board', None, 'city'))

    def test_live_counters_follow_driving(self):
        class Driving:
            def sample(self):
                return 120.0, 2500, 'D', 7

        board = bc.BoardComputer(None, Driving())
        board.select(bc.preset('reset'))
        for _ in range(3600):
            board.advance(1.0)
        p = board.profile
        self.assertAlmostEqual(p['short']['distance'], 120.0, places=3)
        self.assertEqual(p['short']['minutes'], 60)
        self.assertEqual(p['short']['speed'], 120)
        self.assertAlmostEqual(p['short']['cons'], bc.fuel_per_hour(120) / 120 * 100, places=1)
        self.assertEqual(p['range'], 660)
        self.assertIn(p['odometer'], (131, 132))
        self.assertAlmostEqual(p['current_cons'], 7.2)
        board.profile['live'] = False
        board.advance(60.0)
        self.assertEqual(board.profile['short']['minutes'], 60)

    def test_peer_sends_once_a_second(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda _: None, assist_commands=commands)
        now = [50.0]
        peer.assist.board.clock = lambda: now[0]
        commands.put(('@board', None, bc.preset('highway')))
        peer.tick()
        self.assertEqual(rte_messages(peer), [])
        peer.application_running = True
        peer.tick()
        ids = [key for key, _ in rte_messages(peer)]
        self.assertEqual(ids, [bc.SHORT_TERM_ID, bc.TANK_CYCLE_ID, bc.LONG_TERM_ID, bc.RANGE_ID,
                               bc.CURRENT_CONS_ID, bc.ODO_ID, bc.CLOCK_ID])
        peer.outbox.clear()
        now[0] += 0.5
        peer.tick()
        self.assertEqual(rte_messages(peer), [])
        now[0] += 0.6
        peer.tick()
        self.assertEqual(len(rte_messages(peer)), 7)
        peer.outbox.clear()
        commands.put(('@board', None, None))
        peer.tick()
        now[0] += 2
        peer.tick()
        self.assertEqual(rte_messages(peer), [])

    def test_real_ui(self):
        from PySide6.QtWidgets import QApplication
        from ui.board_computer import BoardComputerPanel
        app = QApplication.instance() or QApplication([])

        class Peer:
            def __init__(self):
                self.sent = []

            def set_assist(self, name, field, value):
                self.sent.append((name, field, value))
                return valid_command(name, field, value)

        peer, reports = Peer(), []
        panel = BoardComputerPanel(peer, reports.append)
        panel.presets.setCurrentIndex(panel.presets.findData('reserve'))
        self.assertEqual(peer.sent[-1], ('@board', None, bc.preset('reserve')))
        self.assertEqual(panel.values['range'].value(), 45)
        panel.values['range'].setValue(30)
        self.assertEqual(panel.presets.currentIndex(), 0)
        panel.apply.click()
        self.assertEqual(peer.sent[-1][2]['range'], 30)
        self.assertTrue(valid_command(*peer.sent[-1]))
        panel.stop.click()
        self.assertEqual(peer.sent[-1], ('@board', None, None))
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
