#!/usr/bin/env python3
"""Locate exact ELF32 little-endian vptr literals and nearby ARM STR stores.

This is a triage aid: a literal in an instruction stream is not by itself
a constructor; confirm the LDR and STR in disassembly.
"""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000
DEFAULTS = [0x7c5518, 0x892df0, 0x893098, 0x893450, 0x895458]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    p.add_argument("--vtable", type=lambda s: int(s, 0), action="append")
    args = p.parse_args()
    data = args.elf.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        p.error("expected ELF32 little-endian")
    tables = args.vtable or DEFAULTS
    results = []
    for va in tables:
        needle = struct.pack("<I", va)
        sites = [BASE + i for i in range(0, len(data)-3, 4)
                 if data[i:i+4] == needle]
        def word(addr):
            i = addr - BASE
            return struct.unpack_from("<I", data, i)[0] if 0 <= i <= len(data)-4 else None
        results.append({
            "vtable": hex(va),
            "literal_sites": [hex(s) for s in sites],
            "slot_0x4c": hex(word(va+0x4c)),
            "slot_0x70": hex(word(va+0x70)),
            "slot_0x74": hex(word(va+0x74)),
        })
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
