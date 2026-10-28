#!/usr/bin/env python3
"""Disassemble original GTF2 PT_LOAD without shipping or modifying firmware.

Requires llvm-objdump in PATH. A temporary ELF copy gains only synthetic
section headers, pointing at the original unchanged executable PT_LOAD.
"""
import argparse
import pathlib
import struct
import subprocess
import tempfile

BASE = 0x100000
TEXT_SIZE = 0x9634dc
DEFAULT_RANGES = [(0x122c54, 0x123490), (0x123520, 0x123850)]

def synthetic_elf(original):
    data = bytearray(original)
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError("Expected little-endian ELF32")
    if struct.unpack_from("<H", data, 18)[0] != 40:
        raise ValueError("Expected ARM ELF")
    if len(data) < TEXT_SIZE:
        raise ValueError("Executable PT_LOAD truncated")
    names = b"\0.text\0.shstrtab\0"
    names_offset = len(data)
    data.extend(names)
    data.extend(b"\0" * (-len(data) % 4))
    sh_offset = len(data)
    rows = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (1, 1, 6, BASE, 0, TEXT_SIZE, 0, 0, 4, 0),
        (7, 3, 0, 0, names_offset, len(names), 0, 0, 1, 0),
    ]
    for row in rows:
        data.extend(struct.pack("<10I", *row))
    struct.pack_into("<I", data, 32, sh_offset)
    struct.pack_into("<H", data, 48, 3)
    struct.pack_into("<H", data, 50, 2)
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=pathlib.Path)
    parser.add_argument("--start", type=lambda s: int(s, 0))
    parser.add_argument("--stop", type=lambda s: int(s, 0))
    args = parser.parse_args()
    if (args.start is None) != (args.stop is None):
        parser.error("--start and --stop must be supplied together")
    ranges = [(args.start, args.stop)] if args.start is not None else DEFAULT_RANGES
    for start, stop in ranges:
        if not (BASE <= start < stop <= BASE + TEXT_SIZE):
            parser.error("range outside executable PT_LOAD")
    with tempfile.TemporaryDirectory(prefix="gtf2-disasm-") as temp:
        path = pathlib.Path(temp) / "gtf2-synthetic.elf"
        path.write_bytes(synthetic_elf(args.elf.read_bytes()))
        for start, stop in ranges:
            print(f"\n# ARM disassembly: {start:#x}..{stop:#x}", flush=True)
            subprocess.run(
                ["llvm-objdump", "-d", f"--start-address={start:#x}",
                 f"--stop-address={stop:#x}", str(path)], check=True)

if __name__ == "__main__":
    main()
