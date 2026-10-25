import struct
import unittest
import zlib
from verify_sifs_partitions import parse_table, verify_part, MAGIC


class SifsTests(unittest.TestCase):
    def table(self):
        data = bytearray(0x1000)
        data[0x800:0x808] = b'IFSPTTBL'
        struct.pack_into('<3I', data, 0x808, 2, 2, 120)
        cursor = 0x820
        for name, count in ((b'STAGE2.1', 1), (b'STAGE2.2', 2)):
            struct.pack_into('<8sI', data, cursor, name, count)
            cursor += 12
            for i in range(count):
                struct.pack_into('<8I', data, cursor, i, 1, 0, 20, 8, 32, 0, 0)
                cursor += 32
        return data

    def test_variable_part_records(self):
        table = parse_table(self.table())
        self.assertEqual(table['data_base'], 0x898)
        self.assertEqual([len(p['parts']) for p in table['partitions']], [1, 2])

    def test_table_rejections(self):
        for at, value in ((0x808, 1), (0x80c, 17), (0x810, 119), (0x828, 5)):
            with self.subTest(at=at):
                data = self.table()
                struct.pack_into('<I', data, at, value)
                with self.assertRaises(ValueError):
                    parse_table(data)
        with self.assertRaises(ValueError):
            parse_table(self.table()[:0x897])

    def framed(self):
        body = b'test'
        header = struct.pack('<3I', MAGIC, len(body), 8)
        frame = struct.pack('<I', zlib.adler32(header + body)) + header + body
        return bytearray(frame + b'\0' * 12 + frame), dict(
            compressed=True, stored_size=52, logical_size=16, chunk_size=32)

    def test_chunks_and_partial_last_chunk(self):
        data, part = self.framed()
        result, output = verify_part(data, 0, part)
        self.assertEqual(result['checksums_verified'], 2)
        self.assertEqual(result['output_size'], 16)
        self.assertFalse(result['lzo_verified'])
        self.assertEqual(output, b'')

    def test_corruption_and_bounds(self):
        for at in (0, 4, 8, 16):
            data, part = self.framed()
            data[at] ^= 1
            with self.subTest(at=at), self.assertRaises(ValueError):
                verify_part(data, 0, part)
        data, part = self.framed()
        for field, value in (('stored_size', 53), ('logical_size', 17), ('chunk_size', 16)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_part(data, 0, {**part, field: value})

    def test_uncompressed(self):
        result, output = verify_part(b'abcd', 1, dict(compressed=False, stored_size=2))
        self.assertEqual(output, b'bc')
        self.assertEqual(result['output_size'], 2)


if __name__ == '__main__':
    unittest.main()
