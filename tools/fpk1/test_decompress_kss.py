import unittest

from decompress_kss import lzss_decode


class LzssTests(unittest.TestCase):
    def test_literals_and_back_reference(self):
        # flags 0b00001000: four literals, then a reference of length 6 at distance 4.
        data = bytes([0x08]) + b'abcd' + bytes([6 << 2, 4])
        self.assertEqual(lzss_decode(data, 64), b'abcdabcdab')

    def test_far_distance_uses_low_bits_of_first_byte(self):
        prefix = bytes(range(256)) + bytes(range(4))  # 260 literals
        tokens = bytearray()
        for i in range(0, 256, 8):
            tokens.append(0)
            tokens += prefix[i:i + 8]
        # Last group: four literals, then length 4 at distance 260 (0x104).
        tokens += bytes([0x08]) + prefix[256:] + bytes([(4 << 2) | 1, 0x04])
        out = lzss_decode(bytes(tokens), 512)
        self.assertEqual(out[-4:], prefix[:4])

    def test_rejects_bad_reference_and_overrun(self):
        with self.assertRaises(ValueError):
            lzss_decode(bytes([0x80, 4 << 2, 9]), 64)
        with self.assertRaises(ValueError):
            lzss_decode(bytes([0x08]) + b'abcd' + bytes([63 << 2, 1]), 16)


if __name__ == '__main__':
    unittest.main()
