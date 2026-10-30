"""Local input regression checks: wire fixtures, retries, pacing and Qt route."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import patch

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import gss_ipc_frames as ipc
import kss_peer
from hmi import mfl


class WheelTests(unittest.TestCase):
    def test_wire_order_and_nibbles(self):
        self.assertEqual(mfl.signal(7, 1), bytes.fromhex('01000700'))
        self.assertEqual(mfl.signal(3, 4, 8, 2, 1, 5), bytes.fromhex('24510308'))
        self.assertEqual(mfl.pulse('up')[0], bytes.fromhex('01000600'))
        self.assertEqual(mfl.pulse('down')[0], bytes.fromhex('0f000600'))
        self.assertEqual(mfl.pulse('menu')[0], bytes.fromhex('01000900'))
        self.assertEqual(mfl.pulse('side_left')[0], bytes.fromhex('01000a00'))
        self.assertEqual(mfl.pulse('side_right')[0], bytes.fromhex('01000b00'))
        for action in mfl.ACTIONS:
            self.assertEqual(mfl.pulse(action)[-1], bytes(4))

    def test_ack_and_guest_settle_before_release_and_repeat(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda text: None, wheel_commands=commands)
        peer.application_running = True
        commands.put('ok')
        commands.put('ok')
        signals = []
        with patch('time.monotonic', return_value=1.0) as clock:
            for n in range(6):
                peer.tick()
                frame = peer.next_frame()
                lun, cid, data, last = ipc.parse_frame(frame)[0]
                self.assertEqual((lun, cid, last), (0x11, 0, True))
                self.assertEqual(data[:6], bytes.fromhex('babe00141cc0'))
                signals.append(data[7:-1])
                self.assertEqual(data[-1], 0)
                # No ACK: even large elapsed time cannot release/replace TX.
                clock.return_value += 10
                peer.tick()
                self.assertEqual(peer.next_frame(), frame)
                peer.delivered(frame)
                peer.tick()
                self.assertFalse(peer.outbox)
                clock.return_value += mfl.WheelInput.SETTLE + .001
        self.assertEqual(signals, list(mfl.pulse('ok')) * 2)

    def test_input_before_application_run_is_rejected(self):
        commands = Queue()
        logs = []
        peer = kss_peer.Kss(logs.append, wheel_commands=commands)
        commands.put('view')
        peer.tick()
        self.assertFalse(peer.outbox)
        self.assertIn('not acknowledged', logs[-1])

    def test_qt_buttons_enqueue_kss_actions_without_serial(self):
        from ui import viewer as view_frames
        from PySide6.QtWidgets import QApplication, QToolButton
        app = QApplication.instance() or QApplication([])
        peer = view_frames.KssPeer(Path('/unused'))
        panel = view_frames.WheelPanel(peer, lambda text: None)
        buttons = panel.findChildren(QToolButton)
        for button, (_, _, _, action) in zip(buttons, view_frames.WHEEL_BUTTONS):
            self.assertTrue(button.isEnabled())
            button.click()
            self.assertEqual(peer.wheel_commands.get_nowait(), action)
        peer.stopped = True
        self.assertFalse(peer.send_wheel('ok'))
        disabled = view_frames.WheelPanel(None, lambda text: None)
        self.assertTrue(all(not b.isEnabled() for b in disabled.findChildren(QToolButton)))


if __name__ == '__main__':
    unittest.main()
