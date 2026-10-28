#!/usr/bin/env python3
"""Verify object ownership and three distinct event adapters for gear DP 0x020001f9."""
import argparse,struct
from pathlib import Path
BASE=0x100000
EXPECTED={
 0x266894:0x00056e2c,
 0x5ee2cc:0x0087f808,
 0x87f808:0x005ed688,
 0x87f80c:0x005fdc40,
 0x87f810:0x005fdc28,
 0x87fb38:0x005ed64c,
 0x87fb3c:0x005fdcfc,
 0x87fb40:0x005fdce4,
 0x87f910:0x005ed648,
 0x87f914:0x005fddbc,
 0x87f918:0x005fdda4,
 0x5fdc24:0x020001f9,
 0x5fdce0:0x020001f9,
 0x5fdda0:0x020001f9,
 0x219bdc:0x020001f9,
 0x267064:0xeb0e1c91,
 0x219bac:0xeb121421,
}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("elf",type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little endian")
 for va,want in EXPECTED.items():
  got=struct.unpack_from("<I",b,va-BASE)[0]
  if got!=want:raise ValueError(f"0x{va:x}: got 0x{got:08x}, expected 0x{want:08x}")
 print(f"verified {len(EXPECTED)} ELF instruction/table words")
 print("owner global+0x56e2c -> constructor 0x5ee2b0 -> adapter table 0x87f808")
 print("adapter tables: 0x87f808, 0x87fb38, 0x87f910")
 print("all three event filters compare DP 0x020001f9")
if __name__=="__main__":main()
