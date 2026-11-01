#!/usr/bin/env python3
"""Decode canonical names and factory support for GTF2 provider IDs 1..179."""
import argparse
import csv
import struct
import sys
from pathlib import Path

BASE = 0x100000

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    args = parser.parse_args()
    data = args.elf.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        parser.error("expected ELF32 little-endian")
    def word(va):
        return struct.unpack_from("<I", data, va - BASE)[0]
    writer = csv.writer(sys.stdout)
    writer.writerow(["id", "name", "string_va", "factory_supported"])
    for view_id in range(1, 180):
        case = word(0x25df48 + 4 * (view_id - 1))
        instruction = word(case)
        if (instruction & 0xfffff000) != 0xe59f0000:
            raise ValueError(f"unexpected name case {case:#x}")
        ptr = word(case + 8 + (instruction & 0xfff))
        name = data[ptr - BASE:ptr - BASE + 256].split(b"\0")[0].decode("utf-8", "replace")
        supported = word(0x25a968 + 4 * (view_id - 1)) != 0x25bd7c
        writer.writerow([view_id, name, hex(ptr), int(supported)])

if __name__ == "__main__":
    main()
