"""Local NavigationSD wire fixture, shared ConfigM ownership and real Qt."""
import sys
sys.dont_write_bytecode = True
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from queue import Queue
import unittest

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import gss_ipc_frames as ipc
import kss_peer
from hmi.configm import DEFAULT_CODING
from hmi.driver_assist import valid_command
from hmi.navigation import PRESETS, preset
from hmi.tpms import preset as tpms_preset
from tests.test_traffic_lights import records


class Checks(unittest.TestCase):
    def test_profiles(self):
        for key in PRESETS:
            self.assertTrue(valid_command('@navigation', None, preset(key)))
        for value in ({}, dict(operation=256), dict(operation=True), dict(operation=0, x=1)):
            self.assertFalse(valid_command('@navigation', None, value))
        self.assertFalse(valid_command('@navigation', 'operation', preset('normal')))

    def test_driverassist_media_bit_and_mask_coexist_with_tpms(self):
        peer = kss_peer.Kss(lambda _: None, coding=DEFAULT_CODING, assist_commands=Queue())
        original = list(peer.config_signals)
        base = {key: data for _, key, data in original}
        self.assertFalse(int.from_bytes(base[0x127], 'little') >> 14 & 1)
        nav, tpms = peer.assist.navigation, peer.assist.tpms
        nav.select(preset('normal'))
        tpms.select(tpms_preset('values_24_26'))
        values = {key: data for _, key, data in peer.config_signals}
        self.assertEqual(int.from_bytes(values[0x127], 'little'),
                         int.from_bytes(base[0x127], 'little') | 1 << 14)
        self.assertEqual(int.from_bytes(values[0x12c], 'little'),
                         int.from_bytes(base[0x12c], 'little') | 1 << 5)
        self.assertEqual(nav.availability.mask, 4 | 8)
        peer.outbox.clear()
        nav.select(None)
        self.assertIn((6, 17, (8).to_bytes(4, 'little')), records(peer))
        values = {key: data for _, key, data in peer.config_signals}
        self.assertEqual(values[0x127], base[0x127])
        tpms.select(None)
        self.assertEqual(peer.config_signals, original)

    def test_getall_and_property_requests(self):
        peer = kss_peer.Kss(lambda _: None, assist_commands=Queue())
        nav = peer.assist.navigation
        nav.select(preset('operation_3'))
        peer.outbox.clear()
        for cid, request in ((6, '1c81'), (5, '1c82'), (5, '1c8f')):
            peer.receive(ipc.build_frame([(6, cid, bytes.fromhex(request), True)]))
        replies = records(peer)
        self.assertEqual(nav.get_all(), bytes.fromhex(
            '030032000404' '38014000081c0200' '00' '03' '00' '01' '0000003f'
            '0700' '00000700000000' '000000000007' '00'))
        self.assertIn((6, 6, bytes.fromhex('80263c8103003200')), replies)
        self.assertIn((6, 5, bytes.fromhex('4c82030032000404')), replies)
        self.assertIn((6, 5, bytes.fromhex('4c8f03')), replies)
        peer.outbox.clear()
        # Unsegmented SetGet of the leading MapColorAndType field, then the
        # original segmented MapViewAndOrientation SetGet, whose Reserve
        # bytes must not clear SupportedMapViews.
        frames = (('2cab02',), ('80072cac00000000', 'c0010000'))
        for request in frames:
            for frame in request:
                peer.receive(ipc.build_frame([(6, 5, bytes.fromhex(frame), True)]))
        replies = records(peer)
        self.assertIn((6, 5, bytes.fromhex('4cab0200003f')), replies)
        self.assertIn((6, 5, bytes.fromhex('80074cac00000700')), replies)
        self.assertIn((6, 5, bytes.fromhex('c0010000')), replies)
        self.assertEqual(nav.state[0x2c], bytes([0, 0, 7, 0, 1, 0, 0]))
        peer.outbox.clear()
        for request in ('2cab0000000000', '2c81', '0cf700'):
            peer.receive(ipc.build_frame([(6, 5, bytes.fromhex(request), True)]))
        self.assertFalse(peer.outbox)
        nav.select(None)
        peer.outbox.clear()
        peer.receive(ipc.build_frame([(6, 5, bytes.fromhex('1c8f'), True)]))
        self.assertFalse(peer.outbox)

    def test_real_ui_activation_and_queue_failure(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
        from ui.viewer import KssPeer
        from ui.navigation import NavigationPanel
        self.__class__.app = QApplication.instance() or QApplication([])
        peer = KssPeer(Path('/unused'))
        panel = NavigationPanel(peer, lambda _: None)
        panel.apply.click()
        self.assertEqual(peer.assist_commands.get_nowait(), ('@navigation', None, preset('normal')))
        panel.presets.setCurrentIndex(panel.presets.findData('operation_2'))
        self.assertEqual(peer.assist_commands.get_nowait(), ('@navigation', None, preset('operation_2')))
        self.assertEqual(panel.operation.value(), 2)
        panel.stop.click()
        self.assertEqual(peer.assist_commands.get_nowait(), ('@navigation', None, None))
        peer.stopped = True
        panel.apply.click()
        self.assertTrue(peer.assist_commands.empty())
        disabled = NavigationPanel(None, lambda _: None)
        self.assertFalse(disabled.apply.isEnabled())
        for widget in (panel, disabled, peer):
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == '__main__':
    unittest.main()
