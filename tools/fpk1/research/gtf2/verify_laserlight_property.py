#!/usr/bin/env python3
"""Verify TelltaleHMI_Display DP 0x020002d3 -> Laserlight scene property."""
import argparse,struct
from pathlib import Path
BASE=0x100000
WORDS={0x5bee9c:0x860d09,0x5beea4:0x860d22,0x5beea0:0x1f11c,0x58754c:0x1f11c,0x5bf4b0:0xeb01d3c8,0x5bf4dc:0xeb01d3c3,0x5bf4ec:0xe7846007,0x586d3c:0xeb026ae2}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 little-endian')
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 for va,val in WORDS.items():
  if w(va)!=val:raise ValueError(f'word mismatch {va:#x}: {w(va):#x} != {val:#x}')
 for slot,expected in ((0x5bee9c,'MV_ClusterFull.StatusBar.Laserlight'),(0x5beea4,'Laserlight')):
  addr=w(slot)
  if b[addr-BASE:addr-BASE+len(expected)+1]!=expected.encode()+b'\0':raise ValueError(f'string mismatch {slot:#x}')
 for va,dest in ((0x5bf4b0,0x6343d8),(0x5bf4dc,0x6343f0),(0x586d3c,0x6218cc)):
  ins=w(va);imm=ins&0xffffff
  if imm&0x800000:imm-=0x1000000
  if ins>>24!=0xeb or va+8+imm*4!=dest:raise ValueError(f'bad BL {va:#x}')
 print('verified DP 0x020002d3 handler 0x586d34 -> owner+0x1f11c -> scene MV_ClusterFull.StatusBar.Laserlight -> property Laserlight')
if __name__=='__main__':main()
