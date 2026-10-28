#!/usr/bin/env python3
"""Verify two distinct HMI reactions to RTE IPC-fed DP events.

0x02000230: direct object dirty-bit write.
0x020002d2: two virtual event deliveries, not a direct dirty-bit write.
"""
import argparse,struct
from pathlib import Path
BASE=0x100000
WORDS={
 0x574ea0:0xe1580003,
 0x574ea4:0x0a003e98,
 0x5754ec:0xe1580003,
 0x5754f0:0x0a0045f6,
 0x58490c:0xe59f3be8,
 0x584910:0xe7943003,
 0x584914:0xe5d320e3,
 0x584918:0xe3822001,
 0x58491c:0xe5c320e3,
 0x584920:0xea004cd5,
 0x5854fc:0x0002e7b4,
 0x586cd0:0xe59f3738,
 0x586ce0:0xeb026af9,
 0x586cf0:0xe3a03002,
 0x586cfc:0xe59cc000,
 0x586d00:0xe12fff3c,
 0x586d04:0xe59f3834,
 0x586d0c:0xeb026aee,
 0x586d1c:0xe3a03002,
 0x586d28:0xe59cc000,
 0x586d2c:0xe12fff3c,
 0x586d30:0xea0043d1,
}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path)
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected little-endian ELF32")
 for va,expected in WORDS.items():
  got=struct.unpack_from("<I",b,va-BASE)[0]
  if got!=expected:raise ValueError(f"0x{va:x}: 0x{got:08x} != 0x{expected:08x}")
 print(f"verified {len(WORDS)} exact ARM words")
 print("DP 0x02000230 -> 0x58490c: owner object +0xe3 |= 0x01")
 print("DP 0x020002d2 -> 0x586cd0: two virtual event calls, kind 2")
if __name__=="__main__":main()
