#!/usr/bin/env python3
"""Decode GTF2's 179-way lazy object factory switch at VA 0x25a940.

Outputs the numeric key, ARM jump target, singleton-holder address, and
lazy initializer BL target. The factory's relationship to view IDs is
not assumed; validate callers before assigning symbolic screen names.
"""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000
TABLE = 0x25a968
DEFAULT = 0x25bd7c

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    args = p.parse_args()
    b = args.elf.read_bytes()
    if b[:6] != b"\x7fELF\x01\x01":
        p.error("expected little-endian ELF32")
    def word(va):
        off = va - BASE
        if not 0 <= off <= len(b)-4:
            raise ValueError(f"invalid address {va:#x}")
        return struct.unpack_from("<I", b, off)[0]
    def bl_target(va):
        insn = word(va)
        if insn >> 24 != 0xeb:
            return None
        delta = insn & 0xffffff
        if delta & 0x800000:
            delta -= 0x1000000
        return va + 8 + 4*delta
    rows = []
    for key in range(1, 180):
        case = word(TABLE + 4*(key-1))
        if case == DEFAULT:
            continue
        insn = word(case)
        if (insn & 0xfffff000) != 0xe59f4000:
            raise ValueError(f"unexpected case prologue {case:#x}: {insn:#x}")
        literal = case + 8 + (insn & 0xfff)
        initializer = next((bl_target(a) for a in range(case, case+48, 4)
                            if bl_target(a) is not None), None)
        rows.append({"key":key,"case_va":hex(case),
                     "singleton_holder_va":hex(word(literal)),
                     "initializer_va":hex(initializer) if initializer else None})
    print(json.dumps({"switch_va":hex(0x25a940),"range":"1..179",
                      "supported":len(rows),"default_null":179-len(rows),
                      "rows":rows},indent=2))

if __name__ == "__main__":
    main()
