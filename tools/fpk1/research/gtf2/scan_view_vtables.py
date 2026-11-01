#!/usr/bin/env python3
"""Find candidate GTF2 view vtables with a callable +0x74 entry.

Heuristic only: pointer runs can also occur in non-vtable data. Restrict to
read-only address ranges and confirm candidates using constructor vptr stores.
"""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    p.add_argument("--start", type=lambda x: int(x, 0), default=0x7b0000)
    p.add_argument("--stop", type=lambda x: int(x, 0), default=0x8c0000)
    p.add_argument("--code-stop", type=lambda x: int(x, 0), default=0x7b0000)
    p.add_argument("--min-methods", type=int, default=30)
    args = p.parse_args()
    data = args.elf.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1:
        p.error("expected original ELF32")
    def word(va):
        off = va - BASE
        if off < 0 or off + 4 > len(data):
            return None
        return struct.unpack_from("<I", data, off)[0]
    def code(ptr):
        return ptr is not None and BASE <= ptr < args.code_stop
    found = []
    lo = (args.start + 3) & ~3
    hi = min(args.stop, BASE + len(data) - 0x78)
    for va in range(lo, hi, 4):
        if not code(word(va + 0x74)):
            continue
        count = sum(code(word(va + offset)) for offset in range(0, 0x78, 4))
        if count < args.min_methods:
            continue
        if code(word(va - 4)):
            continue
        found.append({"candidate_va":hex(va), "callable_entries":count,
                      "virtual_0x4c":hex(word(va+0x4c)),
                      "virtual_0x74":hex(word(va+0x74))})
    print(json.dumps({"warning":"heuristic candidates, not proven class vtables",
                      "count":len(found), "candidates":found},indent=2))

if __name__ == "__main__":
    main()
