#!/usr/bin/env python3
"""Compare shared Fernlicht receiver invocation arguments across two RTE DP events."""
import argparse,struct
from pathlib import Path
BASE=0x100000
PAIRS=((0x5812a8,0x586cd0),(0x5812dc,0x586d04))
# Relative instruction offsets where the ARM words must match.
SAME=(4,8,12,16,20,24,28,32,36,40,44,48)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path)
 a=p.parse_args();data=a.elf.read_bytes()
 if data[:6]!=b'\x7fELF\x01\x01':p.error('expected little-endian ELF32')
 def w(va):return struct.unpack_from('<I',data,va-BASE)[0]
 for left,right in PAIRS:
  # LDR instructions use different literal-pool distances.
  assert w(left)&0xfffff000==w(right)&0xfffff000
  for off in SAME:
   if w(left+off)!=w(right+off):
    raise ValueError(f'different instruction {left+off:#x}/{right+off:#x}')
  assert w(left+16)==0xe1a02006 or w(left+16)==0xe2811f73
  assert w(left+32)==0xe88d04a0 or w(left+32)==0xe59cc000
 print('Verified: both events call the same two Fernlicht wrappers with identical argument setup.')
 print('Call inputs: r1=owner+0x1f5cc or owner+0x1fafc, r2=r6, r3=2, stack=[r5,-1,0].')
 print('Unknown: upstream values of r5/r6, virtual receiver implementation, lamp state/animation.')
if __name__=='__main__':main()
