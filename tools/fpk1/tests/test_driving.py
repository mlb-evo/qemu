"""Local driving presets: wire values, pacing through the assist queue and Qt."""
import sys
sys.dont_write_bytecode = True
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from queue import Queue
import unittest

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import kss_peer
from hmi import driving
from hmi.driver_assist import valid_command
from tests.test_tpms import rte_messages


class Checks(unittest.TestCase):
    def test_wire_values(self):
        self.assertEqual(dict(driving.signals(80, 3000, 'D', 3)),
                         {0x21: bytes.fromhex('1f40'), 0x03: bytes.fromhex('0bb8'),
                          0x23: bytes.fromhex('38500000')})
        self.assertEqual(driving.gear_signal('R', 0), bytes.fromhex('06400000'))

    def test_presets_stay_in_range(self):
        for key, (_, state) in driving.PRESETS.items():
            for step in range(0, 1200):
                speed, rpm, selector, gear = state(step * 0.1)
                self.assertTrue(0 <= speed <= 250 and 0 <= rpm <= 7000, key)
                self.assertIn(selector, driving.SELECTOR)
                self.assertTrue(0 <= gear <= 8, key)
        speeds = [driving.PRESETS['sprint'][1](t)[0] for t in range(46)]
        self.assertAlmostEqual(max(speeds), 200)
        self.assertAlmostEqual(speeds[0], 0)

    def test_commands(self):
        self.assertTrue(valid_command('@driving', None, 'city'))
        self.assertTrue(valid_command('@driving', None, None))
        self.assertFalse(valid_command('@driving', None, 'moon'))

    def test_peer_sends_preset_every_period(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda _: None, assist_commands=commands)
        now = [100.0]
        peer.assist.driving.clock = lambda: now[0]
        peer.tick()
        self.assertEqual(rte_messages(peer), [])
        commands.put(('@driving', None, 'park'))
        peer.tick()
        peer.application_running = True
        peer.tick()
        self.assertEqual(rte_messages(peer), [(0x21, bytes.fromhex('000000')),
                                              (0x03, bytes.fromhex('02ee00')),
                                              (0x23, bytes.fromhex('0540000000'))])
        peer.outbox.clear()
        now[0] += 0.05
        peer.tick()
        self.assertEqual(rte_messages(peer), [])
        now[0] += 0.06
        peer.tick()
        self.assertEqual(len(rte_messages(peer)), 3)
        peer.outbox.clear()
        commands.put(('@driving', None, None))
        peer.tick()
        peer.outbox.clear()
        now[0] += 1
        peer.tick()
        self.assertEqual(rte_messages(peer), [])

    def test_real_ui(self):
        from PySide6.QtWidgets import QApplication
        from ui.driving import DrivingPanel
        app = QApplication.instance() or QApplication([])

        class Peer:
            def __init__(self):
                self.sent = []

            def set_assist(self, name, field, value):
                self.sent.append((name, field, value))
                return True

        peer, reports = Peer(), []
        panel = DrivingPanel(peer, reports.append)
        panel.presets.setCurrentIndex(panel.presets.findData('highway'))
        panel.stop.click()
        self.assertEqual(peer.sent, [('@driving', None, 'highway'), ('@driving', None, None)])
        self.assertEqual(panel.presets.currentIndex(), 0)
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
