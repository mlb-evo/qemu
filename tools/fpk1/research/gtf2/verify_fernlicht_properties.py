#!/usr/bin/env python3
"""Verify scene node path and property name pairs used by shared Fernlicht events."""
import argparse,struct
from pathlib import Path
BASE=0x100000
PAIRS=(
 (0x5beed4,'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht',0x5beed8,'Fernlicht',0x5bf6ac,0x5bf6d0),
 (0x5bef14,'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_BIG',0x5bef18,'Fernlicht_BIG',0x5bf864,0x5bf88c),
)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 LE')
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 def target(va):
  ins=w(va);imm=ins&0xffffff
  if imm&0x800000:imm-=0x1000000
  if (ins>>24)&0xf!=0xb:raise ValueError(f'not BL at {va:#x}')
  return va+8+imm*4
 for path_slot,path,prop_slot,prop,path_call,prop_call in PAIRS:
  for slot,expected in ((path_slot,path),(prop_slot,prop)):
   addr=w(slot)
   if b[addr-BASE:addr-BASE+len(expected)+1]!=expected.encode()+b'\0':
    raise ValueError(f'wrong string at {slot:#x}')
  if target(path_call)!=0x6343d8 or target(prop_call)!=0x6343f0:
   raise ValueError(f'wrong setter targets {path_call:#x}/{prop_call:#x}')
  print(f'{path} -> property {prop}')
 assert w(0x6343f4)==0xe2800078
 assert w(0x6343dc)==0xe280008c
 print('verified property-name field +0x78 and scene-path field +0x8c')
if __name__=='__main__':main()
