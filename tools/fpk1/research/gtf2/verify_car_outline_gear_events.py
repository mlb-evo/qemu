#!/usr/bin/env python3
"""Verify extra GTF2 HMI reactions for gear and car-outline IPC fields."""
import argparse,struct
from pathlib import Path
BASE=0x100000
WORDS={
 0x5816ec:0xebf4e5cd,0x5816f0:0xe3a0101f,
 0x5816f8:0xe5933008,0x581700:0xebff7a74,
 0x581708:0xe5933070,0x581710:0xe5d030e4,
 0x581714:0xe3833004,0x581718:0xe5c030e4,
 0x581720:0xe3a01020,0x581740:0xe5d030e4,
 0x581744:0xe3833004,0x581748:0xe5c030e4,
 0x581750:0xe3a01024,
 0x586738:0xebf4d1ba,0x58673c:0xe59f3dcc,
 0x586744:0xe5d320e6,0x586748:0xe3822010,
 0x58674c:0xe5c320e6,0x586750:0xea004549,
 0x586760:0xe5d320e6,0x586764:0xe3822020,
 0x586768:0xe5c320e6,
}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected little-endian ELF32")
 for va,expected in WORDS.items():
  got=struct.unpack_from("<I",b,va-BASE)[0]
  if got!=expected:raise ValueError(f"0x{va:x}: got 0x{got:08x}, expected 0x{expected:08x}")
 print(f"verified {len(WORDS)} ARM instruction words")
 print("Gear DP 0x020001ef: selectors 31,32,36 and receiver +0xe4 bit 2")
 print("CarOutline DP 0x020002ad: object +0xe6 bit 4; adjacent event sets bit 5")
if __name__=="__main__":main()
