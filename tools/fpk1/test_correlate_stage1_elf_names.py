#!/usr/bin/env python3
"""Pure-text path candidate tests."""
import unittest
from correlate_stage1_elf_names import strings

class PathCandidateTests(unittest.TestCase):
    def test_paths_and_coordinates(self):
        raw=b"\x00bin/mount_nand\x00lib/libc.so.3\x00"
        values=strings(raw,0x100)
        self.assertEqual(values[0]["text"],"bin/mount_nand")
        self.assertEqual(values[0]["at"],"0x101")
        self.assertEqual(values[1]["text"],"lib/libc.so.3")
    def test_no_paths(self):
        self.assertEqual(strings(b"\x00\x01\x02",0),[])
if __name__=="__main__":
    unittest.main()
