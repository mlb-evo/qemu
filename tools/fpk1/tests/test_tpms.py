"""Local TPMS wire fixtures, shared BAP ownership, input pacing and real Qt."""
import sys
sys.dont_write_bytecode = True
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from copy import deepcopy
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import patch

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import gss_ipc_frames as ipc
import kss_peer
from hmi.tpms import DEFAULT, PRESETS, preset, properties
from hmi.driver_assist import valid_command
from tests.test_traffic_lights import records
from hmi.configm import DEFAULT_CODING
from hmi.traffic_lights import ONLINE_MASK


def rte_messages(peer):
    result = []
    for lun, cid, stream in records(peer):
        if (lun, cid) != (ipc.LUN_RTE, 0):
            continue
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
    def test_independent_wire_fixtures_and_invalid_ranges(self):
        profile = dict(DEFAULT, state=[1, 2, 3, 4], temperature_state=[5, 6, 7, 8], collected=123)
        values = properties(profile)
        self.assertEqual(values[16], bytes.fromhex('15263748007b'))
        self.assertEqual(values[17], bytes.fromhex('0018181a1aff'))
        self.assertEqual(values[18], bytes.fromhex('0055555555ff'))
        self.assertEqual(values[19], bytes.fromhex('0018181a1aff'))
        for key in PRESETS:
            self.assertTrue(valid_command('@tpms', None, preset(key)))
        for key, value in (('pressure', [256] * 4), ('temperature', [-1] * 4),
                           ('state', [16] * 4), ('temperature_state', [16] * 4),
                           ('required', [1] * 3), ('lamp', 2), ('operation', True)):
            self.assertFalse(valid_command('@tpms', None, dict(DEFAULT, **{key: value})))
        self.assertFalse(valid_command('@tpms', None, {}))
        self.assertFalse(valid_command('@tpms', 'pressure', DEFAULT))

    def test_sessions_coexist_and_restore_original_coding_in_either_order(self):
        for first in ('tpms', 'traffic'):
            peer = kss_peer.Kss(lambda _: None, coding=DEFAULT_CODING, assist_commands=Queue())
            original = list(peer.config_signals)
            t, r = peer.assist.traffic, peer.assist.tpms
            t.select('traffic_red')
            r.select(preset('values_24_26'))
            combined = ONLINE_MASK | 8
            self.assertEqual(r.availability.mask, combined)
            values = {key: data for _, key, data in peer.config_signals}
            base = {key: data for _, key, data in original}
            self.assertEqual(int.from_bytes(values[0x12c], 'little'),
                             int.from_bytes(base[0x12c], 'little') | (1 << 14) | (1 << 5))
            peer.outbox.clear()
            (r.select(None) if first == 'tpms' else t.select('off'))
            remaining = ONLINE_MASK if first == 'tpms' else 8
            self.assertEqual(r.availability.mask, remaining)
            self.assertIn((6, 17, remaining.to_bytes(4, 'little')), records(peer))
            (t.select('off') if first == 'tpms' else r.select(None))
            self.assertEqual(peer.config_signals, original)
            self.assertEqual(r.availability.mask, 0)

    def test_getall_and_property_requests(self):
        peer = kss_peer.Kss(lambda _: None, assist_commands=Queue())
        tpms = peer.assist.tpms
        tpms.select(preset('values_24_26'))
        peer.outbox.clear()
        for request in ('11c1', '11c2', '11c3', '11d1'):
            peer.receive(ipc.build_frame([(6, 7, bytes.fromhex(request), True)]))
        replies = records(peer)
        self.assertEqual(len(tpms.get_all()), 40)
        self.assertIn((6, 7, bytes.fromhex('802831c103010700')), replies)
        self.assertIn((6, 7, bytes.fromhex('41c2030107000403')), replies)
        self.assertIn((6, 7, bytes.fromhex('41d10018181a1aff')), replies)
        self.assertIn((6, 7, bytes.fromhex('800841c33801f000')), replies)
        peer.outbox.clear()
        tpms.select(None)
        peer.outbox.clear()
        peer.receive(ipc.build_frame([(6, 7, bytes.fromhex('11d1'), True)]))
        self.assertFalse(peer.outbox)

    def test_lamp_preserves_other_telltales_and_assist_state(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda _: None, assist_commands=commands)
        peer.application_running = True
        name = 'TelltaleHMI_Display'
        peer.assist.transmit.add(name)
        peer.assist.values[name] = dict(tt_highBeam_b=1)
        from hmi.assist_catalog import SIGNALS
        signal_id = SIGNALS[name][0]
        with patch('time.monotonic', return_value=100.) as clock:
            commands.put(('@tpms', None, preset('lamp_on')))
            peer.tick()
            lamp_data = [value for key, value in rte_messages(peer) if key == signal_id]
            self.assertEqual(lamp_data[-1][0], 0xc0)
            while peer.outbox:
                peer.delivered(peer.next_frame())
            clock.return_value += .151
            commands.put(('@tpms', None, None))
            peer.tick()
            self.assertEqual([value for key, value in rte_messages(peer) if key == signal_id][-1][0], 0x40)
            self.assertEqual(peer.assist.values[name], dict(tt_highBeam_b=1))

    def test_real_ui_presets_manual_apply_and_queue_failure(self):
        from PySide6.QtWidgets import QApplication
        from ui.viewer import KssPeer
        from ui.tpms import TpmsPanel
        self.__class__.app = QApplication.instance() or QApplication([])
        peer = KssPeer(Path('/unused'))
        panel = TpmsPanel(peer, lambda _: None)
        self.assertTrue(peer.assist_commands.empty())
        panel.wheel('side_left')
        self.assertEqual(peer.wheel_commands.get_nowait(), 'side_left')
        panel.presets.setCurrentIndex(panel.presets.findData('lamp_on'))
        self.assertEqual(peer.assist_commands.get_nowait(), ('@tpms', None, preset('lamp_on')))
        panel.controls['pressure', 0].setValue(18)
        self.assertTrue(peer.assist_commands.empty())
        panel.apply.click()
        self.assertEqual(peer.assist_commands.get_nowait()[2]['pressure'][0], 18)
        accepted = deepcopy(panel.accepted)
        for _ in range(peer.assist_commands.maxsize):
            peer.assist_commands.put_nowait(('@tpms', None, None))
        panel.presets.setCurrentIndex(panel.presets.findData('values_30'))
        self.assertEqual(panel.values(), accepted)
        while not peer.assist_commands.empty():
            peer.assist_commands.get_nowait()
        panel.stop.click()
        self.assertEqual(peer.assist_commands.get_nowait(), ('@tpms', None, None))
        peer.stopped = True
        panel.apply.click()
        self.assertTrue(peer.assist_commands.empty())
        panel.close()
        disabled = TpmsPanel(None, lambda _: None)
        self.assertFalse(disabled.apply.isEnabled())
        disabled.close()
        from PySide6.QtCore import QCoreApplication, QEvent
        panel.deleteLater()
        disabled.deleteLater()
        peer.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == '__main__':
    unittest.main()
