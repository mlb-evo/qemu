import struct
import tempfile
import unittest
from pathlib import Path
import zipfile
import zlib

from inspect_stage1_framed import decode_frames, decode_archive, startup_layout, parse_boot_script


def raw_frame(raw):
    return b'ZV\0' + struct.pack('>H', len(raw)) + raw


def compressed_frame(raw, logical):
    return b'ZV\1' + struct.pack('>HH', len(raw), logical) + raw


def command(kind, body):
    length = (4 + len(body) + 3) & ~3
    return struct.pack('<HBB', length, kind, 0) + body + bytes(length - 4 - len(body))


class FramedTests(unittest.TestCase):
    def test_raw_and_compressed_frames(self):
        source = raw_frame(b'A') + compressed_frame(b'\x01BC', 2)
        output, rows = decode_frames(source, 0, len(source))
        self.assertEqual(output, b'ABC')
        self.assertEqual([r['decoded_offset'] for r in rows], [0, 1])

    def test_history_resets_at_frame_boundary(self):
        source = raw_frame(b'A') + compressed_frame(b'\x20\0', 3)
        with self.assertRaisesRegex(ValueError, 'independently'):
            decode_frames(source, 0, len(source))

    def test_bad_frame_extents(self):
        for source in (b'ZV', b'ZV\2\0\1A', b'ZV\0\0\0',
                       b'ZV\0\0\2A', compressed_frame(b'\x01AB', 3)):
            with self.subTest(source=source), self.assertRaises(ValueError):
                decode_frames(source, 0, len(source))
        source = raw_frame(b'AB')
        with self.assertRaisesRegex(ValueError, 'lengths'):
            decode_frames(source, 0, len(source), limit=1)

    def test_archive_length_and_crc(self):
        frame = raw_frame(b'test')
        source = bytearray(0x7f8) + frame + struct.pack('<I', zlib.crc32(b'test'))
        struct.pack_into('<I', source, 0, len(frame) + 4)
        # Padding is outside the length-delimited stream.
        source += bytes(32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.zip'
            for corrupt in (False, True):
                current = bytearray(source)
                if corrupt:
                    current[0x7f8 + len(frame)] ^= 1
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('fixture/stage1_ifs.img', b'HSP' + bytes(0xc2 - 3) + current)
                if corrupt:
                    with self.assertRaisesRegex(ValueError, 'CRC32'):
                        decode_archive(path)
                else:
                    decoded, report = decode_archive(path)
                    self.assertEqual(decoded, b'test')
                    self.assertEqual(report['stream_end'], 0x7f8 + len(frame))

    def startup(self):
        data = bytearray(0x200)
        struct.pack_into('<IHBBHH', data, 8, 0xff7eeb, 1, 1, 0, 256, 40)
        struct.pack_into('<9I', data, 20, 0x80000108, 0, 0x80000008,
                         0x80000008, len(data) - 8, 0x108,
                         len(data) - 8, 0, len(data) - 8 - 0x108)
        struct.pack_into('<H', data, 56, 8)
        self.repair_startup_checksum(data)
        return data

    def repair_startup_checksum(self, data):
        struct.pack_into('<I', data, 0x10c, 0)
        total = sum(x[0] for x in struct.iter_unpack('<I', data[8:0x110]))
        struct.pack_into('<I', data, 0x10c, -total & 0xffffffff)

    def test_startup_size_checksum_and_mapping(self):
        data = self.startup()
        row = startup_layout(data)
        self.assertEqual(row['decoded_imagefs_offset'], 0x110)
        self.assertEqual(row['implied_load_address'], '0x80000000')
        self.assertEqual(row['entry_decoded_offset'], '0x108')
        data[0x108] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            startup_layout(data)
        data = self.startup()
        struct.pack_into('<I', data, 20, 0x90000000)
        self.repair_startup_checksum(data)
        with self.assertRaisesRegex(ValueError, 'entry'):
            startup_layout(data)

    def test_script_external_arguments_and_environment(self):
        metadata = bytes([0, 0x20, 0, 0, 0, 0, 2, 1])
        record = command(0, metadata + b'/bin/app\0app\0--flag\0PATH=/bin\0')
        rows = parse_boot_script(record + bytes(4))
        self.assertEqual(rows[0]['argv'], ['app', '--flag'])
        self.assertEqual(rows[0]['env'], ['PATH=/bin'])
        self.assertTrue(rows[0]['background'])

    def test_script_wait_reopen_and_symlink(self):
        records = (command(4, b'../../lib/libc.so.3\0/usr/lib/ldqnx.so.2\0') +
                   command(1, struct.pack('<H', 50) + b'/dev/example\0') +
                   command(2, struct.pack('<H', 10) + b'/dev/console\0'))
        rows = parse_boot_script(records + bytes(4))
        self.assertEqual(rows[0]['destination'], '/usr/lib/ldqnx.so.2')
        self.assertEqual(rows[1]['maximum_wait_ms'], 5000)
        self.assertEqual(rows[2]['kind'], 'reopen')

    def test_bad_script_records(self):
        for source in (command(9, b'unknown'), command(1, struct.pack('<H', 50) + b'ABCDEFGHIJ') + bytes(4),
                       struct.pack('<HBB', 100, 1, 0), bytes(4) + b'bad',
                       command(0, bytes([0, 0, 0, 0, 0, 0, 5, 0]) + b'/bin/app\0app\0')):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_boot_script(source)


if __name__ == '__main__':
    unittest.main()
