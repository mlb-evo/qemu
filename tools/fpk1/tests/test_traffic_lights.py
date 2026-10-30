"""Local transport/availability checks for the OnlineFunctions fixture."""
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
from hmi.configm import DEFAULT_CODING
from hmi.traffic_lights import status_frames, ONLINE_MASK


def records(peer):
    decoder = ipc.Reassembler()
    return [record for frame in peer.outbox for record in decoder.feed(frame)]


class Checks(unittest.TestCase):
    def test_segmented_property_is_distinct_from_spi_fragmentation(self):
        data = bytes.fromhex('3801e00000000000')
        self.assertEqual(status_frames(3, data),
                         (bytes.fromhex('80084a833801e000'), bytes.fromhex('c000000000')))
        self.assertEqual(status_frames(17, bytes([50, 0, 1])), (bytes.fromhex('4a91320001'),))

    def test_switching_clears_session_and_restores_exact_config(self):
        commands = Queue()
        peer = kss_peer.Kss(lambda _: None, coding=DEFAULT_CODING, assist_commands=commands)
        peer.application_running = True
        original = list(peer.config_signals)
        with patch('time.monotonic', return_value=100.) as clock:
            commands.put(('@scenario', None, 'traffic_red'))
            peer.tick()
            updated = {key: data for _, key, data in peer.config_signals}
            base = {key: data for _, key, data in original}
            self.assertEqual(int.from_bytes(updated[0x12c], 'little'),
                             int.from_bytes(base[0x12c], 'little') | (1 << 14))
            self.assertEqual({key: data for key, data in updated.items() if key != 0x12c},
                             {key: data for key, data in base.items() if key != 0x12c})
            self.assertIn((6, 17, ONLINE_MASK.to_bytes(4, 'little')), records(peer))
            self.assertIn((6, 28, bytes.fromhex('80084a9003000000')), records(peer))
            while peer.outbox:
                peer.delivered(peer.next_frame())
            clock.return_value += .151
            commands.put(('@scenario', None, 'acc'))
            peer.tick()
            self.assertEqual(peer.config_signals, original)
            self.assertIsNone(peer.assist.traffic.profile)
            self.assertIn((6, 17, bytes(4)), records(peer))
            while peer.outbox:
                peer.delivered(peer.next_frame())
            peer.assist.send()
            self.assertTrue(all(lun != 6 for lun, _, _ in records(peer)))

    def test_requests_are_answered_and_empty_base_is_cleared(self):
        peer = kss_peer.Kss(lambda _: None, assist_commands=Queue())
        fixture = peer.assist.traffic
        with patch('time.monotonic', return_value=100.) as clock:
            fixture.select('traffic_red')
            peer.outbox.clear()
            fixture.send()
            packets = [data for lun, cid, data in records(peer) if (lun, cid) == (6, 28)]
            self.assertFalse(any(packet[:2] == bytes.fromhex('4a82') for packet in packets))
            peer.outbox.clear()
            for request in ('1a82', '1a81', '1a83'):
                peer.receive(ipc.build_frame([(6, 28, bytes.fromhex(request), True)]))
            replies = records(peer)
            self.assertIn((6, 28, bytes.fromhex('4a8203002a000300')), replies)
            self.assertEqual(len(fixture.get_all()), 35)
            self.assertTrue(any(data.startswith(bytes.fromhex('80233a81'))
                                for lun, cid, data in replies if (lun, cid) == (6, 28)))
            self.assertIn((6, 28, bytes.fromhex('80084a833801e000')), replies)
            count = len(peer.outbox)
            peer.receive(ipc.build_frame([(6, 28, bytes.fromhex('1a80'), True)]))
            peer.receive(ipc.build_frame([(6, 27, bytes.fromhex('1a82'), True)]))
            self.assertEqual(len(peer.outbox), count)
            peer.outbox.clear()
            fixture.select('off')
            self.assertEqual(peer.config_signals, [])
            self.assertIn(ipc.rte_signal(0x12c, bytes(2)), records(peer))


if __name__ == '__main__':
    unittest.main()
