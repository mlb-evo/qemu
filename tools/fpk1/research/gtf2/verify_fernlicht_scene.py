#!/usr/bin/env python3
"""Prove two shared RTE receiver wrappers are configured for Fernlicht scene nodes."""
import argparse,struct
from pathlib import Path
BASE=0x100000
CHECK={0x5bf68c:0xe51f17c0,0x5bf6ac:0xeb01d349,0x5bf6dc:0xe51f9808,0x5bf6f4:0xe7840009,0x5bf84c:0xe51f1940,0x5bf864:0xeb01d2db,0x5bf898:0xe51f1984,0x5bf8a0:0xe784b001,0x5812a8:0xe59f38d4,0x5812dc:0xe59f38a4,0x586cd0:0xe59f3738,0x586d04:0xe59f3834}
SLOTS={0x5beed4:'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht',0x5bef14:'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_BIG'}
OFFSETS={0x5beedc:0x1f5d0,0x5bef1c:0x1fb00,0x581b84:0x1f5d0,0x581b88:0x1fb00,0x587410:0x1f5d0,0x587540:0x1fb00}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 little endian')
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 for va,value in {**CHECK,**OFFSETS}.items():
  if w(va)!=value:raise ValueError(f'word at {va:#x}: {w(va):#x} != {value:#x}')
 for slot,s in SLOTS.items():
  va=w(slot)
  if b[va-BASE:va-BASE+len(s)+1]!=s.encode()+b'\x00':raise ValueError(f'scene path mismatch {slot:#x}')
 for slot,expected in [(0x5beed4,0x5bf68c),(0x5bef14,0x5bf84c),(0x5beedc,0x5bf6dc),(0x5bef1c,0x5bf898),(0x581b84,0x5812a8),(0x581b88,0x5812dc),(0x587410,0x586cd0),(0x587540,0x586d04)]:
  ins=w(expected)
  if ins&0x0f7f0000!=0x051f0000:raise ValueError(f'not PC LDR {expected:#x}')
  got=expected+8+(ins&4095 if ins&0x800000 else -(ins&4095))
  if got!=slot:raise ValueError(f'wrong literal slot {expected:#x} -> {got:#x}')
 print('verified: 0x1f5d0 -> Fernlicht; 0x1fb00 -> Fernlicht_BIG')
 print('both shared event handlers access the exact same two owner fields')
 print('not proven: which payload bits affect lamp state or animations')
if __name__=='__main__':main()
