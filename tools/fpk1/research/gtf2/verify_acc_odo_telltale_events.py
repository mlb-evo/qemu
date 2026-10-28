#!/usr/bin/env python3
"""Verify GTF2 HMI event paths for ACC, odometer, and telltale DP IDs."""
import argparse
import struct
from pathlib import Path

BASE=0x100000
WORDS={
 0x575128:0x02000297,0x575144:0x020002c2,0x5750f0:0x0200021d,
 0x574dcc:0xe59f331c,0x574dd0:0xe1580003,0x574dd4:0x0a003c85,
 0x583ff0:0xe51f3744,0x583ff8:0xeb027633,0x584024:0xe59cc000,
 0x57535c:0xe51f323c,0x575360:0xe1580003,0x575364:0x0a004438,
 0x575498:0xe51f335c,0x57549c:0xe1580003,0x5754a0:0x0a004531,
 0x58644c:0xe51f3ef8,0x586454:0xeb026d1c,0x586480:0xe59cc000,
 0x58696c:0xebf4d12d,0x586980:0xe5d32006,0x586984:0xe3822008,
 0x586988:0xe5c32006,0x586998:0xe5d32006,0x58699c:0xe3822008,
 0x5869a0:0xe5c32006,0x5869b0:0xeb026bc5,
 0x5873dc:0x0004a54c,0x5873e0:0x00050834,0x5873e4:0x0004a8e4,
}
BRANCHES={0x575364:0x58644c,0x5754a0:0x58696c,0x574dd4:0x583ff0}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path)
 args=p.parse_args()
 data=args.elf.read_bytes()
 if data[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little-endian")
 def word(va):return struct.unpack_from("<I",data,va-BASE)[0]
 for va,expected in WORDS.items():
  got=word(va)
  if got!=expected:raise ValueError(f"0x{va:x}: 0x{got:08x} != 0x{expected:08x}")
 for va,dest in BRANCHES.items():
  ins=word(va)
  delta=ins&0xffffff
  if delta&0x800000:delta-=0x1000000
  actual=va+8+delta*4
  if actual!=dest:raise ValueError(f"0x{va:x}: 0x{actual:x} != 0x{dest:x}")
 print(f"verified {len(WORDS)} ARM words and {len(BRANCHES)} event branches")
 print("ACC_HMI_Display DP 0x02000297 -> 0x58644c: virtual event delivery")
 print("TelltaleHMI_Display DP 0x0200021d -> 0x583ff0: virtual event delivery")
 print("ODO_HMI_Distance DP 0x020002c2 -> 0x58696c: two object flags |= 8, virtual event")
if __name__=="__main__":main()
