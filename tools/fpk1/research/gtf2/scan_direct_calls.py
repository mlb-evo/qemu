#!/usr/bin/env python3
"""Locate direct ARM-state BL call sites in an extracted FPK1 GTF2 ELF.

Usage: python3 tools/fpk1/research/gtf2/scan_direct_calls.py /path/to/gtf2 --target 0x699594
Scans file-backed executable PT_LOAD ranges. This is an instruction-pattern scan,
not a full control-flow disassembler; data embedded in text may yield false positives.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def inspect(path, target):
    data = path.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Expected ELF32 little-endian")
    phoff, = struct.unpack_from("<I", data, 28)
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    if phentsize != 32 or phnum > 256 or phoff + phnum * phentsize > len(data):
        raise ValueError("Invalid program header table")
    sites = []
    for i in range(phnum):
        typ, off, va, _, filesz, memsz, flags, _ = struct.unpack_from(
            "<8I", data, phoff + 32 * i)
        if typ != 1 or not flags & 1:
            continue
        if off + filesz > len(data):
            raise ValueError("Truncated executable segment")
        for rel in range(0, filesz - 3, 4):
            word, = struct.unpack_from("<I", data, off + rel)
            # ARM-state BL immediate: cond != 0xf; bits 27..24 == 1011.
            if (word & 0x0f000000) != 0x0b000000 or word >> 28 == 15:
                continue
            imm = word & 0xffffff
            if imm & 0x800000:
                imm -= 0x1000000
            site = va + rel
            dest = (site + 8 + imm * 4) & 0xffffffff
            if dest == target:
                sites.append(dict(site_va=hex(site), instruction=hex(word),
                                  target_va=hex(dest)))
    return dict(sha256=hashlib.sha256(data).hexdigest(), target_va=hex(target),
                direct_bl_sites=sites,
                limitation="ARM-state direct BL pattern scan only; no indirect calls or dynamic execution.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--target", type=lambda s: int(s, 0), default=0x699594)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = json.dumps(inspect(args.elf, args.target), indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")

if __name__ == "__main__":
    main()
