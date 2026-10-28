#!/usr/bin/env python3
"""Read-only ARM32 ELF DT_INIT_ARRAY inventory for FPK1 GTF2.

Usage: python3 tools/fpk1/research/gtf2/inspect_init_array.py /path/to/bin/gtf2
Outputs JSON; does not export firmware bytes or modify input.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def inspect(path):
    data = path.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Expected little-endian ELF32")
    phoff, = struct.unpack_from("<I", data, 28)
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    if phentsize != 32 or phnum > 256 or phoff + phnum * phentsize > len(data):
        raise ValueError("Invalid ELF program header table")
    loads = []
    for i in range(phnum):
        typ, off, va, _, fs, ms, flags, _ = struct.unpack_from("<8I", data, phoff + i * phentsize)
        if typ == 1:
            if off + fs > len(data):
                raise ValueError("Truncated LOAD")
            loads.append(dict(offset=off, vaddr=va, filesz=fs, memsz=ms, flags=flags))
    def read_va(va, size):
        for p in loads:
            if p["vaddr"] <= va and va + size <= p["vaddr"] + p["filesz"]:
                at = p["offset"] + va - p["vaddr"]
                return data[at:at + size], at
        raise ValueError(f"Virtual range not backed by ELF file: {va:#x}")
    # Firmware-specific dynamic metadata, checked against the ELF program headers.
    array_va, array_size = 0x00a644dc, 1408
    raw, file_offset = read_va(array_va, array_size)
    pointers = struct.unpack("<" + "I" * (array_size // 4), raw)
    rows = []
    for index, pointer in enumerate(pointers):
        owner = next((p for p in loads if p["vaddr"] <= pointer < p["vaddr"] + p["memsz"]), None)
        rows.append(dict(index=index, entry_va=array_va + index * 4,
                         target_va=pointer,
                         segment_flags=owner["flags"] if owner else None,
                         executable=bool(owner and owner["flags"] & 1)))
    return dict(input_sha256=hashlib.sha256(data).hexdigest(),
                input_size=len(data), init_array_va=array_va,
                init_array_file_offset=file_offset, init_array_bytes=array_size,
                entries=len(rows), unique_targets=len(set(pointers)),
                executable_targets=sum(row["executable"] for row in rows),
                constructors=rows)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = json.dumps(inspect(args.elf), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")

if __name__ == "__main__":
    main()
