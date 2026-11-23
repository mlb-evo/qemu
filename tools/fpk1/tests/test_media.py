"""Local AudioSD wire fixture, ConfigM ownership and real Qt."""
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
from hmi.media import PRESETS, preset, properties
from hmi.navigation import preset as nav_preset
from tests.test_traffic_lights import records


class Checks(unittest.TestCase):
    def test_profiles(self):
        for key in PRESETS:
            self.assertTrue(valid_command('@media', None, preset(key)))
        bad = preset('radio_fm')
        bad['primary'] = 'x' * 128
        for value in ({}, bad, dict(preset('radio_fm'), playing=1), dict(preset('radio_fm'), mute=256)):
            self.assertFalse(valid_command('@media', None, value))

    def test_layouts(self):
        values = properties(preset('media_usb'))
        # SourceType 0x0f, SourceList_Reference 1 (LE), nibbles, Number.
        self.assertEqual(values[0x10], bytes.fromhex('0f0100000000'))
        self.assertEqual(values[0x11], b'\x03USB')
        self.assertEqual(values[0x34], bytes.fromhex('2a00f5000000'))
        self.assertEqual(values[0x15], b'\x0cSunset Drive\x48\x00\x00' b'\x10The Midnight Run\x49'
                         b'\x0bNight Roads\x4a' b'\x00\x00' b'\x00\x00\x00' b'\x00\x00')
        self.assertEqual(values[3], bytes.fromhex('3801dc0000000800'))

    def test_audio_bit_and_mask_coexist_with_navigation(self):
        peer = kss_peer.Kss(lambda _: None, coding=DEFAULT_CODING, assist_commands=Queue())
        original = list(peer.config_signals)
        base = {key: data for _, key, data in original}
        media, nav = peer.assist.media, peer.assist.navigation
        media.select(preset('radio_fm'))
        nav.select(nav_preset('normal'))
        values = {key: data for _, key, data in peer.config_signals}
        self.assertEqual(int.from_bytes(values[0x127], 'little'),
                         int.from_bytes(base[0x127], 'little') | 1 << 5 | 1 << 14)
        self.assertEqual(media.availability.mask, 2 | 4)
        media.select(None)
        nav.select(None)
        self.assertEqual(peer.config_signals, original)

    def test_getall_and_property_requests(self):
        peer = kss_peer.Kss(lambda _: None, assist_commands=Queue())
        media = peer.assist.media
        media.select(preset('radio_fm'))
        peer.outbox.clear()
        for cid, request in ((4, '1c41'), (3, '1c42'), (4, '1c55')):
            peer.receive(ipc.build_frame([(6, cid, bytes.fromhex(request), True)]))
        replies = records(peer)
        self.assertIn((6, 3, bytes.fromhex('4c42030031000404')), replies)
        self.assertTrue(any(cid == 4 and data[:1] == b'\x80' and data[2:4] == bytes.fromhex('3c41')
                            for _, cid, data in replies))
        self.assertTrue(any(cid == 4 and data[2:4] == bytes.fromhex('4c55') for _, cid, data in replies))
        info = properties(preset('radio_fm'))[0x15]
        self.assertIn(len(info).to_bytes(2, 'little') + info, media.get_all())

    def test_station_list_available(self):
        # ListAvailable bit 0 (ReceptionList) in the radio presets only.
        self.assertEqual(properties(preset('radio_fm'))[0x10], bytes.fromhex('020100010000'))
        self.assertEqual(properties(preset('media_usb'))[0x10][3], 0)

    def test_play_position_ticks(self):
        peer = kss_peer.Kss(lambda _: None, assist_commands=Queue())
        media = peer.assist.media
        media.select(preset('media_usb'))
        peer.outbox.clear()
        media.next_tick = 0
        media.tick()
        self.assertEqual(media.profile['position'], 43)
        self.assertIn((6, 3, bytes.fromhex('4c74') + bytes.fromhex('2b00f5000000')), records(peer))

    def test_panel(self):
        from PySide6.QtWidgets import QApplication
        from ui.media import MediaPanel
        app = QApplication.instance() or QApplication([])
        sent = []

        class Peer:
            def set_assist(self, name, field, value):
                sent.append((name, field, value))
                return True
        panel = MediaPanel(Peer(), lambda _: None)
        panel.presets.setCurrentIndex(panel.presets.findData('media_usb'))
        self.assertEqual(sent[-1], ('@media', None, preset('media_usb')))
        panel.fields['primary'].setText('Other track')
        panel.apply.click()
        self.assertEqual(sent[-1][2]['primary'], 'Other track')
        panel.stop.click()
        self.assertEqual(sent[-1], ('@media', None, None))
        app.processEvents()


if __name__ == '__main__':
    unittest.main()
