#!/usr/bin/env python3
"""Decode GTF2 mode-indexed view-ID lists and compare with the object factory."""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    a = p.parse_args()
    data = a.elf.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        p.error("expected ELF32 little-endian")
    def word(va):
        off = va - BASE
        if off < 0 or off + 4 > len(data):
            raise ValueError(hex(va))
        return struct.unpack_from("<I", data, off)[0]
    supported = {i for i in range(1, 180)
                 if word(0x25a968 + 4 * (i-1)) != 0x25bd7c}
    rows = []
    for mode in range(1, 17):
        pointer = word(0x8169b8 + 4 * (mode-1))
        ids = []
        if pointer:
            for index in range(180):
                value = word(pointer + index*4)
                if value == 0:
                    break
                if not 1 <= value <= 179:
                    raise ValueError(f"mode {mode}: invalid ID {value}")
                ids.append(value)
            else:
                raise ValueError(f"mode {mode}: missing terminator")
        rows.append(dict(mode=mode, table_va=hex(pointer) if pointer else None,
                         count=len(ids), ids=ids,
                         duplicate_count=len(ids)-len(set(ids)),
                         supported_overlap=len(set(ids)&supported),
                         unsupported_ids=sorted(set(ids)-supported),
                         missing_supported_ids=sorted(supported-set(ids))))
    print(json.dumps(dict(factory_supported=len(supported), modes=rows), indent=2))

if __name__ == "__main__":
    main()
