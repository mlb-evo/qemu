#!/usr/bin/env python3
"""Synthetic regression tests for NAME coordinate mappings."""
import unittest
from map_stage1_name_record_coordinates import examine

class CoordinateTests(unittest.TestCase):
    def test_names_without_elf(self):
        data=b"\x00NAME=one\x00DESCRIPTION=First\x00NAME=two\x00DESCRIPTION=Second\x00"
        report=examine(data)
        self.assertEqual(report["name_count"],2)
        self.assertEqual([r["name"] for r in report["name_records"]],["one","two"])
        self.assertTrue(all(r["preceding_strict_elf"] is None for r in report["name_records"]))
    def test_no_metadata(self):
        report=examine(b"\x00\x01\x02")
        self.assertEqual(report["name_count"],0)
        self.assertEqual(report["strict_elf_count"],0)

if __name__=="__main__":unittest.main()
