"""Local checks for coherent scenarios, clearing old states and simple Qt UI."""
import sys
sys.dont_write_bytecode = True
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import patch

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import kss_peer
from research.hmi.assist_catalog import SIGNALS
from research.hmi.assist_scenarios import LABELS, scenario
from research.hmi.driver_assist import pack, valid_command
from research.hmi.check_driver_assist import messages


class Checks(unittest.TestCase):
    def test_scenarios_have_consistent_legacy_and_hmi_requests(self):
        for key in LABELS:
            profile = scenario(key)
            for name, fields in profile.items():
                for field, value in fields.items():
                    self.assertTrue(valid_command(name, field, value), (key, name, field))
                self.assertEqual(len(pack(name, fields)), SIGNALS[name][1])
        for key in ('acc', 'follow', 'gap', 'acc_lane'):
            profile = scenario(key)
            self.assertEqual(profile['ACC_KBI']['available'], 1)
            self.assertEqual(profile['ACC_HMI_Display']['acc_DisplayTimeGap_b'], 1)
            self.assertEqual(profile['ACC_02']['ACC_Anzeige_Zeitluecke_uint8'], 1)
            self.assertEqual(profile['ACC_HMI_Display']['acc_desiredSpeed_uint16'],
                             profile['ACC_02']['ACC_Wunschgeschw_uint16'])
            self.assertEqual(profile['ACC_HMI_Display']['acc_SetTimeGap_uint8'],
                             profile['ACC_02']['ACC_Gesetzte_Zeitluecke_uint8'])

    def test_one_command_applies_snapshot_and_off_clears_old_channels(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda text: None, assist_commands=commands)
        peer.application_running = True
        commands.put(('@scenario', None, 'follow'))
        with patch('time.monotonic', return_value=10.) as clock:
            peer.tick()
            self.assertTrue(commands.empty())
            actual = dict(messages(peer))
            self.assertEqual(actual[0x293], b'\1\0')
            self.assertEqual(len(actual), 10)
            commands.put(('@scenario', None, 'off'))
            peer.tick()
            self.assertEqual(dict(messages(peer)), actual)
            while peer.outbox:
                peer.delivered(peer.next_frame())
            clock.return_value += .151
            peer.tick()
            self.assertFalse(peer.assist.transmit)
            self.assertEqual(set(dict(messages(peer))), set(actual))
            self.assertTrue(all(not any(value) for _, value in messages(peer)))

    def test_simple_ui_sends_one_transaction_and_advanced_is_optional(self):
        from PySide6.QtWidgets import QApplication
        from view_frames import KssPeer
        from research.hmi.assist_ui import AssistPanel
        app = QApplication.instance() or QApplication([])
        peer = KssPeer(Path('/unused'))
        window = AssistPanel(peer, lambda text: None)
        self.assertTrue(window.tabs.isHidden())
        self.assertTrue(window.search.isHidden())
        index = window.scenario.findData('acc_lane')
        window.scenario.setCurrentIndex(index)
        self.assertEqual(peer.assist_commands.get_nowait(), ('@scenario', None, 'acc_lane'))
        self.assertTrue(peer.assist_commands.empty())
        self.assertTrue(window.enables['ACC_HMI_Display'].isChecked())
        self.assertTrue(window.controls['LDW_02', 'LDW_Status_LED_gruen_uint8'].isChecked())
        window.advanced.setChecked(True)
        self.assertFalse(window.tabs.isHidden())
        peer.stopped = True
        window.scenario.setCurrentIndex(window.scenario.findData('off'))
        self.assertEqual(window.scenario.currentIndex(), index)
        self.assertTrue(peer.assist_commands.empty())
        window.close()

    def test_two_main_tabs_keep_log_and_state_without_another_window(self):
        from PySide6.QtWidgets import QApplication
        from view_frames import KssPeer, PeerWindow, Viewer
        app = QApplication.instance() or QApplication([])
        for make in (lambda peer: PeerWindow(peer),
                     lambda peer: Viewer(Path('/unused.ppm'), Path('/unused'), peer)):
            peer = KssPeer(Path('/unused.sock'))
            window = make(peer)
            self.assertEqual([window.tabs.tabText(i) for i in range(window.tabs.count())],
                             ['Лог и руль', 'Driver assist'])
            self.assertIs(window.tabs.widget(1), window.assist)
            self.assertFalse(window.assist.isWindow())
            self.assertIs(window.assist.window(), window)
            window.tabs.setCurrentIndex(1)
            index = window.assist.scenario.findData('follow')
            window.assist.scenario.setCurrentIndex(index)
            self.assertEqual(peer.assist_commands.get_nowait(), ('@scenario', None, 'follow'))
            peer.line.emit('message while assist tab is active')
            window.tabs.setCurrentIndex(0)
            self.assertIn('message while assist tab is active', window.kss_log.toPlainText())
            window.tabs.setCurrentIndex(1)
            self.assertEqual(window.assist.scenario.currentIndex(), index)
            self.assertTrue(peer.assist_commands.empty())
            window.close()


if __name__ == '__main__':
    unittest.main()
