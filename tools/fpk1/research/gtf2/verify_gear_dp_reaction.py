#!/usr/bin/env python3
"""Verify GTF2 Gear_Display DP 0x020001f9 consumer control-flow edges.

Uses only ELF32 little-endian ARM words. The consumer is a conditional
event-ID filter followed by a state query, a virtual +0x70 call and a
state/notification helper. No display-render claim is implied.
"""
import argparse
import struct
from pathlib import Path

BASE=0x100000
EDGES={
 0x5fdbf0:0x122498,
 0x5fdb98:0x219b78,
 0x5fdbcc:0x6528f0,
 0x219bac:0x69ec38,
 0x652914:0x63669c,
 0x652938:0x14cb48,
}
WORDS={
 0x5fdbf4:0xe5941004, # LDR r1,[r4,#4]
 0x5fdbf8:0xe59f3024, # LDR r3,[pc,#0x24]
 0x5fdbfc:0xe1510003, # CMP r1,r3
 0x5fdc20:0xeaffffd9, # B 0x5fdb8c
 0x5fdc24:0x020001f9, # DP ID
 0x5fdba8:0xe5933070, # LDR r3,[r3,#0x70]
 0x5fdbbc:0xe5933070, # same virtual slot, alternate path
 0x5fdbb4:0xe3a01001, # state flag 1
 0x5fdbc8:0xe1a01005, # state flag 0 (r5=0)
 0x6528f4:0xe5d031b8, # read object flag +0x1b8
 0x65294c:0xe5d030f8, # read cached flag +0xf8
 0x652950:0xe5c410f8, # store new flag +0xf8
}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path)
 a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little-endian")
 def word(va):return struct.unpack_from("<I",b,va-BASE)[0]
 for va,expected in WORDS.items():
  got=word(va)
  if got!=expected:raise ValueError(f"word at 0x{va:x}: 0x{got:08x} != 0x{expected:08x}")
 for va,target in EDGES.items():
  ins=word(va)
  if ins&0x0f000000!=0x0b000000:raise ValueError(f"not BL at 0x{va:x}")
  delta=ins&0xffffff
  if delta&0x800000:delta-=0x1000000
  got=va+8+delta*4
  if got!=target:raise ValueError(f"BL at 0x{va:x} -> 0x{got:x}, expected 0x{target:x}")
 print(f"verified {len(WORDS)} ARM words and {len(EDGES)} BL edges")
 print("DP 0x020001f9 event filter -> 0x5fdb8c -> virtual +0x70 -> 0x6528f0")
if __name__=="__main__":main()
