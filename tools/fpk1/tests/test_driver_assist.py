"""Local assist checks: independent wire fixtures, ownership, pacing and Qt."""
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
import gss_ipc_frames as ipc
import kss_peer
from hmi.driver_assist import pack, valid_command
from hmi.assist_catalog import SIGNALS


def messages(peer):
    reassembler = ipc.Reassembler()
    stream = b''.join(data for frame in peer.outbox for _, _, data in reassembler.feed(frame))
    result = []
    while stream:
        assert stream[:2] == b'\xba\xbe'
        size = (stream[2] << 6) | (stream[3] >> 2)
        key = (stream[4] << 4) | (stream[5] >> 4)
        value = stream[7:7 + size]
        assert len(value) == size and ipc.crc8(value) == stream[6]
        result.append((key, value))
        stream = stream[7 + size:]
    return result


class Checks(unittest.TestCase):
    def test_original_wire_fixtures_and_range_checks(self):
        self.assertEqual(pack('ACC_KBI', {'available': 1}), b'\1')
        self.assertEqual(pack('ZPM_HMI_Info', {'ZPM_warnID_unit16': 0xa800}),
                         bytes.fromhex('00a80000000000000000'))
        self.assertEqual(pack('HMI_C_NightVision_Parameters', {'NV_imageYoffset_sint8': -1}),
                         bytes.fromhex('00000000ff'))
        for name, (_, size, fields) in SIGNALS.items():
            self.assertEqual(pack(name, {}), bytes(size))
            for field, bits, signed in fields:
                self.assertTrue(valid_command(name, field, 0))
                self.assertFalse(valid_command(name, field, 1 << len(bits)))
        self.assertFalse(valid_command('missing', None, True))

    def test_default_does_not_transmit_and_ack_retains_changes(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda text: None, assist_commands=commands)
        peer.application_running = True
        peer.tick()
        self.assertFalse(peer.outbox)
        commands.put(('ACC_KBI', 'available', 1))
        peer.tick()
        self.assertFalse(peer.outbox)
        commands.put(('ACC_KBI', None, True))
        with patch('time.monotonic', return_value=10.) as clock:
            peer.tick()
            self.assertEqual(messages(peer), [(0x293, b'\1\0')])
            commands.put(('ACC_KBI', 'available', 0))
            clock.return_value = 20.
            peer.tick()
            self.assertEqual(messages(peer), [(0x293, b'\1\0')])
            peer.delivered(peer.next_frame())
            peer.tick()
            self.assertFalse(peer.outbox)
            clock.return_value += .151
            peer.tick()
            self.assertEqual(messages(peer), [(0x293, b'\0\0')])

    def test_all_enabled_messages_reassemble_and_warning_has_one_owner(self):
        peer = kss_peer.Kss(lambda text: None, assist_commands=Queue())
        peer.application_running = True
        peer.assist.transmit = set(SIGNALS)
        peer.assist.values['ZPM_HMI_Info']['ZPM_warnID_unit16'] = 0xa800
        peer.closures.send()
        closure = messages(peer)
        self.assertEqual([key for key, _ in closure], [0x10, 0x1c2])
        while peer.outbox:
            peer.delivered(peer.next_frame())
        peer.assist.send()
        got = messages(peer)
        self.assertEqual(len(got), len(SIGNALS))
        self.assertEqual({key for key, _ in got}, {row[0] for row in SIGNALS.values()})
        self.assertEqual(dict(got)[0x272][1:3], bytes.fromhex('a800'))
        self.assertTrue(all(value[-1] == 0 for _, value in got))

    def test_real_qt_controls_queue_and_rollback(self):
        from PySide6.QtWidgets import QApplication
        from ui.viewer import KssPeer
        from ui.assist import AssistPanel
        app = QApplication.instance() or QApplication([])
        peer = KssPeer(Path('/unused'))
        window = AssistPanel(peer, lambda text: None)
        self.assertEqual(len(window.controls), 126)
        self.assertTrue(peer.assist_commands.empty())
        checkbox = window.controls['ACC_KBI', 'available']
        checkbox.click()
        self.assertEqual(peer.assist_commands.get_nowait(), ('ACC_KBI', 'available', 1))
        window.enables['ACC_KBI'].click()
        self.assertEqual(peer.assist_commands.get_nowait(), ('ACC_KBI', None, True))
        peer.stopped = True
        checkbox.click()
        self.assertTrue(checkbox.isChecked())
        self.assertTrue(peer.assist_commands.empty())
        window.close()


if __name__ == '__main__':
    unittest.main()
