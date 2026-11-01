#!/usr/bin/env python3
"""Decode GTF2's own MFL steering-wheel key -> HMI event tables.

The ARM mapper at 0x18c82c uses the key index table at 0x7da8a4
(36 u32 entries), a 16-byte button classifier at 0x7d9d30 and a
16 x 6 event-ID matrix at 0x7da5a8. A 0xffffffff matrix cell means
no mapped event; index 8 has a separate rotary/tick path.
"""
import argparse
import struct
from pathlib import Path

BASE = 0x100000
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    a = p.parse_args()
    b = a.elf.read_bytes()
    if b[:6] != b"\x7fELF\x01\x01": p.error("expected ELF32 little endian")
    def u32(addr): return struct.unpack_from("<I", b, addr-BASE)[0]
    indices = [u32(0x7da8a4+4*i) for i in range(36)]
    buttons = b[0x7d9d30-BASE:0x7d9d30-BASE+16]
    matrix = [[u32(0x7da5a8+24*i+4*j) for j in range(6)] for i in range(16)]
    print("keycode  index  kind    evcode=1  2  3  4  5  6")
    for key, idx in enumerate(indices):
        if idx == 16:
            print(f"{key:>7}  invalid")
            continue
        kind = "button" if buttons[idx] else "rotary"
        values = ["-" if x == 0xffffffff else str(x) for x in matrix[idx]]
        print(f"{key:>7} {idx:>6}  {kind:<6}  "+" ".join(f"{v:>4}" for v in values))
if __name__ == "__main__": main()
