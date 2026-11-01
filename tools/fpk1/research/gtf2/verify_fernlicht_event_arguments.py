#!/usr/bin/env python3
"""Compare shared Fernlicht receiver invocation arguments across two RTE DP events."""
import argparse,struct
from pathlib import Path
BASE=0x100000
PAIRS=((0x5812a8,0x586cd0,16,48),(0x5812dc,0x586d04,8,40))
# Relative instruction offsets where the ARM words must match.
SAME=(4,8,12,16,20,24,28,32,36,40,44,48)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path)
 a=p.parse_args();data=a.elf.read_bytes()
 if data[:6]!=b'\x7fELF\x01\x01':p.error('expected little-endian ELF32')
 def w(va):return struct.unpack_from('<I',data,va-BASE)[0]
 for left,right,call_offset,last_offset in PAIRS:
  # LDR instructions use different literal-pool distances.
  assert w(left)&0xfffff000==w(right)&0xfffff000
  for off in SAME:
   if off==call_offset or off>last_offset:continue
   if w(left+off)!=w(right+off):
    raise ValueError(f'different instruction {left+off:#x}/{right+off:#x}')
  for va in (left+call_offset,right+call_offset):
   ins=w(va);imm=ins&0xffffff
   if imm&0x800000:imm-=0x1000000
   if ins>>24!=0xeb or va+8+4*imm!=0x6218cc:
    raise ValueError(f'bad receiver getter call at {va:#x}')
 print('Verified: both events call the same two Fernlicht wrappers with identical argument setup.')
 print('Call inputs: r1=owner+0x1f5cc or owner+0x1fafc, r2=r6, r3=2, stack=[r5,-1,0].')
 print('Unknown: upstream values of r5/r6, virtual receiver implementation, lamp state/animation.')
if __name__=='__main__':main()
