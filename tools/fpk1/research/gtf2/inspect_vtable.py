#!/usr/bin/env python3
"""Inspect a candidate GTF2 vtable and exact pointer cross-references.

Works with the original GTF2 ELF (VA 0x100000 -> file offset 0).
Results are candidates, not proof of C++ dynamic type.
"""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--vtable", type=lambda x: int(x, 0), default=0x891958)
    parser.add_argument("--entries", type=int, default=21)
    args = parser.parse_args()
    data = args.elf.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1:
        parser.error("Expected ELF32")
    def word(va):
        off = va - BASE
        if off < 0 or off + 4 > len(data):
            raise ValueError(f"VA outside file: {va:#x}")
        return struct.unpack_from("<I", data, off)[0]
    rows = [{"slot": f"+{i*4:#04x}", "function_va":hex(word(args.vtable+i*4))}
            for i in range(args.entries)]
    refs = [hex(BASE+i) for i in range(0,len(data)-3,4)
            if struct.unpack_from("<I", data, i)[0] == args.vtable]
    print(json.dumps({"vtable_va":hex(args.vtable),
                      "pointer_literal_sites":refs,"entries":rows},indent=2))
if __name__ == "__main__":
    main()
