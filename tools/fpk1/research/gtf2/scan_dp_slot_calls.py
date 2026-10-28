#!/usr/bin/env python3
"""Find direct ARM BL callsites of GTF2-owned DP-slot functions.

The scan covers only the executable PT_LOAD and does not disassemble libraries.
A callsite is not a complete call graph: virtual BLX and function pointers
are deliberately outside this direct-branch inventory.
"""
import argparse
import collections
import json
import struct
from pathlib import Path

BASE = 0x100000
TEXT_SIZE = 0x9634dc
TARGETS = {
    0x120e94: "enable_dp_slot",
    0x122338: "disable_and_flush_dp_slot",
    0x11c8ec: "insert_dp_id_in_slot",
    0x1213e0: "language_change_mark_all",
    0x123520: "gtf2_event_dispatcher",
}

def scan(data):
    if data[:4] != b"\x7fELF" or len(data) < TEXT_SIZE:
        raise ValueError("Not the expected complete GTF2 ELF")
    result = collections.defaultdict(list)
    for offset in range(0, TEXT_SIZE - 3, 4):
        insn = struct.unpack_from("<I", data, offset)[0]
        # ARM B/BL: bits[27:25]=101 and link bit[24]=1.
        # Exclude unconditional BLX-immediate (condition 0xf).
        if (insn & 0x0f000000) != 0x0b000000:
            continue
        immediate = insn & 0xffffff
        if immediate & 0x800000:
            immediate -= 1 << 24
        destination = BASE + offset + 8 + (immediate << 2)
        if destination in TARGETS:
            result[destination].append(BASE + offset)
    return {
        TARGETS[dest]: {"target": hex(dest), "callsites": [hex(v) for v in result[dest]]}
        for dest in TARGETS
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.elf.read_bytes()), indent=2))

if __name__ == "__main__":
    main()
