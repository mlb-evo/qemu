import unittest

import gss_ipc_frames as f


class FrameTests(unittest.TestCase):
    def test_empty_frame_matches_gss_ipc_layout(self):
        frame = f.empty_frame()
        self.assertEqual(len(frame), 128)
        self.assertEqual(frame[0], 0)
        self.assertTrue(all(b == 0xff for b in frame[1:127]))
        self.assertTrue(f.valid(frame))
        self.assertEqual(f.parse_frame(frame), [])

    def test_records_round_trip_and_header_count(self):
        frame = f.build_frame([(7, 3, b'\x01\x02', True), (7, 11, b'\x00', True)])
        self.assertEqual(frame[0], 3 + 2 + 3 + 1)
        self.assertEqual(frame[1:4], bytes([2, 7, 3 | 0x80]))
        self.assertEqual(f.parse_frame(frame), [(7, 3, b'\x01\x02', True), (7, 11, b'\x00', True)])

    def test_checksum_is_inverted_byte_sum(self):
        frame = bytearray(f.build_frame([(7, 1, b'\x05', True)]))
        self.assertEqual(frame[127], ~sum(frame[:127]) & 0xff)
        frame[5] ^= 1
        self.assertFalse(f.valid(bytes(frame)))
        with self.assertRaises(ValueError):
            f.parse_frame(bytes(frame))

    def test_fragments_reassemble_across_frames(self):
        message = bytes(range(250))
        pieces = f.fragment(7, 4, message)
        self.assertGreater(len(pieces), 1)
        assembler = f.Reassembler()
        out = []
        for piece in pieces:
            out += assembler.feed(f.build_frame([piece]))
        self.assertEqual(out, [(7, 4, message)])

    def test_rejects_oversize_and_bad_layout(self):
        with self.assertRaises(ValueError):
            f.build_frame([(7, 3, bytes(124), True)])
        bad = bytearray(f.empty_frame())
        bad[0] = 10
        bad[127] = f.checksum(bad)
        with self.assertRaises(ValueError):
            f.parse_frame(bytes(bad))

    def test_mode_request_payload(self):
        lun, cid, payload = f.gss_mode_request(1, 2)
        self.assertEqual((lun, cid, payload[:2], len(payload)), (7, 3, b'\x01\x02', 18))


class L4cTests(unittest.TestCase):
    def test_crc_matches_gss_ipc_table(self):
        # First bytes of gss_ipc's table at 0x1b5cac are crc8 of single bytes.
        table = bytes.fromhex('001d3a2774694e53e8f5d2cf9c81a6bb')
        self.assertEqual(bytes(f.crc8([i]) for i in range(16)), table)

    def test_header_matches_a_gss_ipc_record(self):
        # GSS -> KSS record seen on LUN 0x11: dataID 0x311, two zero bytes.
        self.assertEqual(f.l4c_message(0x311, b'\x00\x00'), bytes.fromhex('babe00083110000000'))
        message = f.l4c_message(0x24d, b'\x01\x02\x03', priority=1)
        self.assertEqual(message[2:6], bytes([0, 3 << 2 | 1, 0x24, 0xd0]))
        self.assertEqual(message[6], f.crc8(b'\x01\x02\x03'))

    def test_versions_info_layout(self):
        info = f.vs_versions_info(part_number=b'8S0906961AK', sw_version=b'0378', zpm_version=0x102, flags=2)
        self.assertEqual(len(info), 56)
        self.assertEqual(info[:5], bytes([2, 1, 2, 0, 0]))
        self.assertEqual(info[20:31], b'8S0906961AK')
        self.assertEqual(info[42:46], b'0378')
        lun, cid, message = f.rte_signal(f.L4C_VS_HMI_VERSIONS_INFO, info)
        self.assertEqual((lun, cid, len(message), message[-1]), (0x11, 0, 7 + 57, 0))

if __name__ == '__main__':
    unittest.main()
