#!/usr/bin/env python3
"""Regression: ARM exception unwind segment is standard and permitted."""
import struct
import unittest
from validate_stage1_unseeded_lzf import scan_elf

def synthetic_elf(program_type):
    b=bytearray(0x200)
    b[:16]=b"\x7fELF\x01\x01\x01"+b"\x00"*9
    struct.pack_into("<HHI",b,16,2,40,1)
    struct.pack_into("<IIII",b,24,0x10000,52,0,0)
    struct.pack_into("<HHHHHH",b,40,52,32,2,0,0,0)
    struct.pack_into("<IIIIIIII",b,52,1,0x100,0x10000,0x10000,32,32,5,0x100)
    struct.pack_into("<IIIIIIII",b,84,program_type,0x120,0x10020,0x10020,16,16,4,4)
    return b

class ArmProgramHeaderTests(unittest.TestCase):
    def test_pt_arm_exidx(self):
        item=scan_elf(synthetic_elf(0x70000001))[0]
        self.assertTrue(item["strict_elf_valid"], item["rejection_reasons"])
    def test_pt_arm_archext(self):
        item=scan_elf(synthetic_elf(0x70000000))[0]
        self.assertTrue(item["strict_elf_valid"], item["rejection_reasons"])
    def test_unknown_processor_type_rejected(self):
        item=scan_elf(synthetic_elf(0x70000002))[0]
        self.assertFalse(item["strict_elf_valid"])
        self.assertIn("unknown_program_type:0x70000002",item["rejection_reasons"])

if __name__=="__main__":
    unittest.main()
