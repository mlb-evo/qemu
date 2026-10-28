#!/usr/bin/env python3
"""Prove that two distinct GTF2 DP handlers share two event receivers."""
import argparse
import struct
from pathlib import Path

BASE = 0x100000
WORDS = {
    0x6218cc: 0xe59000b8, 0x6218d0: 0xe12fff1e,
    0x581b84: 0x0001f5d0, 0x581b88: 0x0001fb00,
    0x587410: 0x0001f5d0, 0x587540: 0x0001fb00,
    0x5812bc: 0xe2841b7d, 0x5812c4: 0xe2811f73,
    0x5812e8: 0xe2841b7e, 0x5812ec: 0xe2811fbf,
    0x586ce4: 0xe2841b7d, 0x586cec: 0xe2811f73,
    0x586d10: 0xe2841b7e, 0x586d14: 0xe2811fbf,
    0x5812d8: 0xe12fff3c, 0x581304: 0xe12fff3c,
    0x586d00: 0xe12fff3c, 0x586d2c: 0xe12fff3c,
    0x5812c8: 0xe3a03002, 0x5812f4: 0xe3a03002,
    0x586cf0: 0xe3a03002, 0x586d1c: 0xe3a03002,
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    args = parser.parse_args()
    data = args.elf.read_bytes()
    if data[:6] != b'\x7fELF\x01\x01':
        parser.error('expected little-endian ELF32')
    for va, expected in WORDS.items():
        got = struct.unpack_from('<I', data, va - BASE)[0]
        if got != expected:
            raise ValueError(f'0x{va:x}: 0x{got:08x} != 0x{expected:08x}')
    print(f'verified {len(WORDS)} instruction and literal words')
    print('DP 0x020001e6 and 0x020002d2 share receiver slots 0x1f5d0, 0x1fb00')
    print('matching context offsets: 0x1f5cc, 0x1fafc; both event kind 2')
    print('0x6218cc returns wrapper->field_0xb8; virtual call uses resulting pointer')

if __name__ == '__main__':
    main()
