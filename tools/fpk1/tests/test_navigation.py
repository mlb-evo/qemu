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
        self.assertEqual(nav.get_all(), bytes.fromhex('030032000404') + bytes.fromhex('3801000000000000') + b'\0\3')
        self.assertIn((6, 6, bytes.fromhex('80103c8103003200')), replies)
        self.assertIn((6, 5, bytes.fromhex('4c82030032000404')), replies)
        self.assertIn((6, 5, bytes.fromhex('4c8f03')), replies)
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
        panel.wheel('right')
        self.assertEqual(peer.wheel_commands.get_nowait(), 'right')
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
