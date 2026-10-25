import io
from pathlib import Path
import re
import struct
import tempfile
import unittest

from create_fpk1_emmc import DISK_SIZE, NAND_BASE, SECTOR, blank_volume, layout, write_tables
from probe_stage1_startup import build_atags
from run_stage1_console import BOARD_CMDLINE, summarize_log

MIB = 1 << 20


def partitions(disk):
    """Walk MBR primaries then the EBR chain, as QNX numbers t177 instances."""
    def read(sector):
        disk.seek(sector * SECTOR)
        block = disk.read(SECTOR)
        assert block[510:] == b'\x55\xaa'
        return [struct.unpack_from('<4xB3xII', block, 446 + 16 * i) for i in range(4)]
    found, extended = [], None
    for kind, start, count in read(0):
        if kind == 5:
            extended = start
        elif kind:
            found.append((kind, start, count))
    current = extended
    while current is not None:
        rows = read(current)
        kind, start, count = rows[0]
        found.append((kind, current + start, count))
        current = extended + rows[1][1] if rows[1][0] == 5 else None
    return found


class EmmcLayoutTests(unittest.TestCase):
    def test_eight_type_177_partitions_in_fstab_order(self):
        rows = layout(200 * MIB, 200 * MIB)
        # Only table sectors matter; emulate the 1 GiB disk with a sparse dict.
        sectors = {}

        class Sparse(io.RawIOBase):
            pos = 0

            def seek(self, offset, whence=0):
                self.pos = offset
                return offset

            def write(self, data):
                sectors[self.pos // SECTOR] = bytes(data)
                return len(data)

            def read(self, size):
                return sectors.get(self.pos // SECTOR, bytes(size))

        stream = Sparse()
        write_tables(stream, rows)
        found = partitions(stream)
        self.assertEqual([(177, start, count) for _, start, count in rows], found)
        self.assertEqual([label for label, _, _ in rows][3:],
                         ['persist_swdl', 'temp_fpk', 'persist_fpk', 'stage3', 'app'])
        ends = [start + count for _, start, count in rows]
        self.assertTrue(all(end <= nxt for end, (_, nxt, _) in zip(ends, rows[1:])))
        self.assertGreaterEqual(rows[0][1] * SECTOR, NAND_BASE + 9 * MIB)
        self.assertLessEqual(ends[-1] * SECTOR, DISK_SIZE)

    def test_rejects_oversized_partitions(self):
        with self.assertRaises(ValueError):
            layout(600 * MIB, 600 * MIB)

    def test_blank_volume_spans_partition_with_valid_superblocks(self):
        with tempfile.TemporaryDirectory() as directory:
            target = 4 * MIB
            blank = blank_volume(Path(directory), target, inode_slack=31)
        self.assertEqual(len(blank), target)
        primary = blank[0x2000:0x2200]
        self.assertEqual(struct.unpack_from('<I', primary)[0], 0x68191122)
        blocksize, inodes, _, blocks = struct.unpack_from('<IIII', primary, 0x30)
        self.assertEqual(inodes, 2 + 31)  # root, dumps and the spare inodes
        backup = (blocks + 3) * blocksize
        self.assertEqual(struct.unpack_from('<I', blank, backup)[0], 0x68191122)


class ConsoleRunTests(unittest.TestCase):
    def test_board_cmdline_matches_quickboot_formats(self):
        self.assertRegex(BOARD_CMDLINE, r'nvsku=\d{3}-\d{5}-\d{4}-\d{3} SkuVer=..')
        self.assertRegex(BOARD_CMDLINE, r'ProdInfo=\d{3}-\d{5}-\d{4}-\d{3} ProdVer=..')
        project, sku = map(int, re.search(r'nvsku=\d+-(\d+)-(\d+)-', BOARD_CMDLINE).groups())
        self.assertIn(project, (0xf19c, 0xf1a2))
        self.assertEqual(sku, 5)
        self.assertTrue(BOARD_CMDLINE.startswith('mem=512M@0x80000000 '))
        self.assertTrue(BOARD_CMDLINE.endswith(' '))
        build_atags(BOARD_CMDLINE)

    def test_log_summary_groups_values(self):
        text = ('System Registers: unimplemented device write (size 4, offset 0x010, value=0x1)\n'
                'System Registers: unimplemented device write (size 4, offset 0x010, value=0x2)\n'
                'tegra30_clk_read: unimplemented read offset 0x004c\n')
        rows = summarize_log(text)
        self.assertEqual(rows[0]['count'], 2)
        self.assertIn('value=*', rows[0]['line'])
        self.assertEqual(len(rows), 2)


if __name__ == '__main__':
    unittest.main()
