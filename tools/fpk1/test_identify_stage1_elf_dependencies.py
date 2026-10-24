#!/usr/bin/env python3
"""Synthetic ELF32 ARM dynamic-table tests, without proprietary input."""
import struct
import unittest
from identify_stage1_elf_dependencies import inspect_elf

class IdentifyELFTests(unittest.TestCase):
    def test_dynamic_strings(self):
        data = bytearray(1024)
        data[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<H", data, 16, 3)
        struct.pack_into("<I", data, 24, 0x1100)
        struct.pack_into("<I", data, 28, 52)
        struct.pack_into("<H", data, 44, 3)
        struct.pack_into("<IIIIIIII", data, 52, 1, 0, 0x1000, 0, 1024, 1024, 5, 4)
        struct.pack_into("<IIIIIIII", data, 84, 2, 0x180, 0x1180, 0, 48, 48, 4, 4)
        struct.pack_into("<IIIIIIII", data, 116, 3, 0x280, 0x1280, 0, 16, 16, 4, 1)
        entries = [(5,0x1200),(10,64),(1,1),(14,13),(0,0)]
        for i,(tag,value) in enumerate(entries):
            struct.pack_into("<II",data,0x180+8*i,tag,value)
        data[0x200:0x200+32] = b"\0libc.so.3\0libsample.so\0" + b"\0"*8
        data[0x280:0x280+11] = b"/usr/lib/ld\0"
        result=inspect_elf(data,0)
        self.assertEqual(result["elf_type"],"ET_DYN")
        self.assertEqual(result["dynamic_strings"]["needed"],["libc.so.3"])
        self.assertEqual(result["dynamic_strings"]["soname"],["libsample.so"])
        self.assertEqual(result["interpreter"],["/usr/lib/ld"])

    def test_missing_string_table(self):
        data=bytearray(256)
        struct.pack_into("<I",data,28,52)
        struct.pack_into("<H",data,44,1)
        struct.pack_into("<IIIIIIII",data,52,1,0,0x1000,0,256,256,5,4)
        result=inspect_elf(data,0)
        self.assertEqual(result["dynamic_strings"]["needed"],[])

if __name__=="__main__":
    unittest.main()
