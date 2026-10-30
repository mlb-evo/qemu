"""Local checks for closure wire bits, persistent state and real Qt toggles."""
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
from hmi.closures import CLOSURES, signal, updates


def payload(frame):
    lun, cid, data, last = ipc.parse_frame(frame)[0]
    assert (lun, cid, last) == (0x11, 0, True)
    assert data[:6] == bytes.fromhex('babe000c0100')
    assert data[9] == 0
    assert data[10:16] == bytes.fromhex('babe00081c20')
    assert data[17] == int(bool(data[7]))
    assert data[18] == 0
    warning = bytes.fromhex('00a80000000000000000') if data[7] else bytes(10)
    assert data[19:] == ipc.l4c_message(0x272, warning + b'\0')
    return data[7:9]


class Checks(unittest.TestCase):
    def test_active_tracks_any_opening_in_the_same_l4c_stream(self):
        for mask in (0, 1, 2, 4, 8, 16, 32, 63):
            stream = updates(mask)
            self.assertEqual(stream[:10], ipc.l4c_message(0x10, bytes([mask, 0, 0])))
            self.assertEqual(stream[10:19], ipc.l4c_message(0x1c2, bytes([int(mask != 0), 0])))
            warning = bytes.fromhex('00a80000000000000000') if mask else bytes(10)
            self.assertEqual(stream[19:], ipc.l4c_message(0x272, warning + b'\0'))

    def test_independent_wire_fixtures(self):
        expected = {'front_left': '0100', 'front_right': '0200',
                    'rear_left': '0400', 'rear_right': '0800',
                    'boot': '1000', 'bonnet': '2000'}
        for name, _, bit in CLOSURES:
            self.assertEqual(signal(1 << bit).hex(), expected[name])
        self.assertEqual(signal(63), b'\x3f\x00')
        with self.assertRaises(ValueError):
            signal(64)

    def test_changes_preserve_other_openings_and_wait_for_ack(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda text: None, closure_commands=commands)
        peer.application_running = True
        for change in [('front_left', True), ('boot', True), ('front_left', False)]:
            commands.put(change)
        with patch('time.monotonic', return_value=10.) as clock:
            for expected in (b'\x01\x00', b'\x11\x00', b'\x10\x00'):
                peer.tick()
                frame = peer.next_frame()
                self.assertEqual(payload(frame), expected)
                clock.return_value += 1
                peer.tick()
                self.assertEqual(len(peer.outbox), 1)
                peer.delivered(frame)
                peer.tick()
                self.assertFalse(peer.outbox)
                clock.return_value += .151

    def test_preboot_state_is_repeated_after_application_run(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda text: None, closure_commands=commands)
        commands.put(('bonnet', True))
        peer.tick()
        self.assertFalse(peer.outbox)
        peer.application_running = True
        peer.last_alive = 0
        peer.tick()
        frame = peer.outbox[-1]
        self.assertEqual(payload(frame), b'\x20\x00')
        while peer.outbox:
            peer.delivered(peer.next_frame())
        peer.last_alive = 0
        peer.tick()
        self.assertEqual(payload(peer.outbox[-1]), b'\x20\x00')

    def test_qt_open_close_and_reject_rollback(self):
        from PySide6.QtWidgets import QApplication
        from ui.viewer import KssPeer, ClosurePanel
        app = QApplication.instance() or QApplication([])
        peer = KssPeer(Path('/unused'))
        panel = ClosurePanel(peer, lambda line: None)
        self.assertEqual(len(panel.buttons), 6)
        for name, button in panel.buttons.items():
            self.assertFalse(button.isChecked())
            button.click()
            self.assertTrue(button.isChecked())
            self.assertTrue(button.text().endswith(': Open'))
            self.assertEqual(peer.closure_commands.get_nowait(), (name, True))
            button.click()
            self.assertEqual(peer.closure_commands.get_nowait(), (name, False))
            self.assertTrue(button.text().endswith(': Closed'))
        peer.stopped = True
        panel.buttons['boot'].click()
        self.assertFalse(panel.buttons['boot'].isChecked())
        self.assertTrue(panel.buttons['boot'].text().endswith(': Closed'))
        self.assertTrue(peer.closure_commands.empty())
        disabled = ClosurePanel(None, lambda line: None)
        self.assertTrue(all(not b.isEnabled() for b in disabled.buttons.values()))

    def test_configuration_and_closures_coexist_at_startup_and_alive(self):
        from hmi.configm import DEFAULT_CODING, all_signals, parse_coding
        peer = kss_peer.Kss(lambda text: None, coding=DEFAULT_CODING)
        peer.handle(7, ipc.CID_GSS_STATUS, b'\x01')
        startup = [ipc.parse_frame(frame)[0][2] for frame in peer.outbox]
        expected = [ipc.l4c_message(key, value + b'\0')
                    for _, key, value in all_signals(parse_coding(DEFAULT_CODING))]
        for message in expected:
            self.assertIn(message, startup)
        self.assertEqual(payload(peer.outbox[-1]), b'\0\0')
        while peer.outbox:
            peer.delivered(peer.next_frame())
        peer.last_alive = 0
        peer.tick()
        repeated = [ipc.parse_frame(frame)[0][2] for frame in peer.outbox]
        for message in expected:
            self.assertIn(message, repeated)
        self.assertEqual(payload(peer.outbox[-1]), b'\0\0')


if __name__ == '__main__':
    unittest.main()
