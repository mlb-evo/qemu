#!/usr/bin/env python3
"""Verify shared selector DP and allowed values in Gear_Display state gate."""
import argparse
import struct
from pathlib import Path

BASE=0x100000
PREDICATES={
 0x2183cc:(0x2183f8,(10,5)),
 0x218478:(0x2184a4,(15,9)),
 0x21839c:(0x2183c8,(14,2)),
}
CALLS={0x219b80:0x2183cc,0x219b8c:0x218478,
       0x219b98:0x21839c,0x219bac:0x69ec38}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path)
 a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected little-endian ELF32")
 def word(va):return struct.unpack_from("<I",b,va-BASE)[0]
 for fn,(literal,values) in PREDICATES.items():
  assert word(literal)==0x06400dc6,(hex(fn),"DP literal")
  assert word(fn+12)==0xe59f0000+(literal-(fn+20)),(hex(fn),"LDR literal")
  assert word(fn+16)&0x0f000000==0x0b000000,(hex(fn),"DP read call")
  assert word(fn+20)==0xe1dd00f6,(hex(fn),"signed 16-bit read")
  assert word(fn+24)==0xe3500000+values[0],(hex(fn),"first CMP")
  assert word(fn+28)==0x13500000+values[1],(hex(fn),"second CMP")
 for va,target in CALLS.items():
  ins=word(va)
  assert ins&0x0f000000==0x0b000000,hex(va)
  delta=ins&0xffffff
  if delta&0x800000:delta-=0x1000000
  assert va+8+delta*4==target,(hex(va),hex(target))
 assert word(0x219bdc)==0x020001f9
 print("verified 3 selector predicates, 4 BL edges, and Gear_Display DP literal")
 print("selector DP 0x06400dc6 in {2,5,9,10,14,15}; then nonzero DP 0x020001f9")
if __name__=="__main__":main()
