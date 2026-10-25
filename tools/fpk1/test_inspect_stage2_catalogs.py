import struct
import unittest

from inspect_stage2_catalogs import parse_catalog, dependency_coverage
from verify_sifs_partitions import verify_archive


def record(mode, name, target=None, offset=0x200, size=8):
    prefix = 32 if mode & 0xf000 == 0x8000 else 24
    tail = name.encode() + b'\0'
    if target is not None:
        prefix = 28
        tail += target.encode() + b'\0'
    length = (prefix + len(tail) + 3) & ~3
    data = bytearray(length)
    struct.pack_into('<HHII', data, 0, length, 0, 1, mode)
    if prefix == 32:
        struct.pack_into('<II', data, 24, offset, size)
    elif target is not None:
        struct.pack_into('<HH', data, 24, len(name.encode()) + 1, len(target.encode()))
    data[prefix:prefix + len(tail)] = tail
    return data


def checksum(data):
    struct.pack_into('<I', data, len(data) - 4, 0)
    total = sum(x[0] for x in struct.iter_unpack('<I', data))
    struct.pack_into('<I', data, len(data) - 4, -total & 0xffffffff)
    return data


def image(records=None):
    if records is None:
        records = [record(0o40755, ''), record(0o100755, 'bin/app'),
                   record(0o120777, 'bin/sh', '../lib/core.so')]
    data = bytearray(0x240)
    data[:8] = b'imagefs\x04'
    struct.pack_into('<III', data, 8, len(data), 0x200, 0x5c)
    catalog = b''.join(records)
    data[0x5c:0x5c + len(catalog)] = catalog
    data[0x200:0x208] = b'payload!'
    return checksum(data)


class CatalogTests(unittest.TestCase):
    def test_root_regular_and_symlink(self):
        rows = parse_catalog(image())['entries']
        self.assertEqual([r['path'] for r in rows], ['', 'bin/app', 'bin/sh'])
        self.assertEqual(rows[1]['offset'], 0x200)
        self.assertEqual(rows[2]['target'], '../lib/core.so')

    def test_checksum_and_header(self):
        data = image()
        data[0x200] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            parse_catalog(data)
        data = image()
        struct.pack_into('<I', data, 8, len(data) - 4)
        with self.assertRaisesRegex(ValueError, 'extents'):
            parse_catalog(checksum(data))

    def test_names_and_duplicate_paths(self):
        for name in ('../outside', '/absolute', 'a/../b', 'a//b', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_catalog(image([record(0o100644, name)]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            parse_catalog(image([record(0o40755, ''), record(0o40755, '')]))

    def test_record_and_file_bounds(self):
        for offset, size in ((0x100, 8), (0x23c, 4), (0x200, 0xffffffff)):
            with self.subTest(offset=offset, size=size), self.assertRaises(ValueError):
                parse_catalog(image([record(0o100644, 'file', offset=offset, size=size)]))
        data = image()
        struct.pack_into('<H', data, 0x5c, 0x400)
        with self.assertRaisesRegex(ValueError, 'extent'):
            parse_catalog(checksum(data))

    def test_bad_symlink_lengths_and_termination(self):
        for name_size, target_size in ((1000, 9), (7, 1000), (0, 9), (7, 8)):
            link = record(0o120777, 'bin/sh', '/bin/ksh')
            struct.pack_into('<HH', link, 24, name_size, target_size)
            # Correct target length is 8; corrupt that case's final NUL too.
            if (name_size, target_size) == (7, 8):
                link[28 + 7 + 8] = 65
            with self.subTest(name_size=name_size, target_size=target_size), self.assertRaises(ValueError):
                parse_catalog(image([link]))

    def test_missing_terminator(self):
        data = image()
        parsed = parse_catalog(data)
        # Bound the directory exactly at the last record, excluding terminator.
        struct.pack_into('<I', data, 12, parsed['catalog_end'])
        with self.assertRaisesRegex(ValueError, 'terminator'):
            parse_catalog(checksum(data))

    def test_coverage_is_basename_presence(self):
        images = [dict(name='fixture', inspection=dict(
            entries=[dict(path='lib/libfixture.so', kind='symlink', target='libfixture.so.1')],
            elf_files=[dict(path='bin/app', dynamic_strings=dict(needed=['libfixture.so', 'libabsent.so']))]))]
        rows = {r['name']: r for r in dependency_coverage(images)}
        self.assertEqual(rows['libfixture.so']['catalog_basename_matches'][0]['kind'], 'symlink')
        self.assertEqual(rows['libabsent.so']['catalog_basename_matches'], [])

    def test_callback_requires_complete_image(self):
        with self.assertRaisesRegex(ValueError, 'decompression'):
            verify_archive('unused', inspect_image=lambda image: {})


if __name__ == '__main__':
    unittest.main()
