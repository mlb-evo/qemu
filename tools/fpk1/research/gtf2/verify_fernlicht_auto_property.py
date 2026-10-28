#!/usr/bin/env python3
"""Verify TelltaleHMI_Display field +0 -> DP 0x020002ce -> three scene properties."""
import argparse,struct
from pathlib import Path
BASE=0x100000
PROPS=(
 (0x1f5d0,'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht','Fernlicht'),
 (0x1f868,'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_AUTO','Fernlicht_AUTO'),
 (0x1fb00,'MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_BIG','Fernlicht_BIG'),
)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes();w=lambda va:struct.unpack_from('<I',b,va-BASE)[0]
 assert b[:6]==b'\x7fELF\x01\x01'
 assert w(0x57514c)==0x020002d2
 assert w(0x5754f8)==0xe2433004
 assert w(0x5754fc)==0xe1580003
 assert w(0x575504)==0xea0045cd
 assert w(0x587410)==0x1f5d0 and w(0x587414)==0x1f868 and w(0x587540)==0x1fb00
 assert w(0x5bef08)==0x1f868
 for slot,s in ((0x5beef4,PROPS[1][1]),(0x5beef8,PROPS[1][2])):
  addr=w(slot);assert b[addr-BASE:addr-BASE+len(s)+1]==s.encode()+b'\0'
 def branch(va):
  x=w(va);imm=x&0xffffff
  if imm&0x800000:imm-=0x1000000
  return (x>>24,va+8+imm*4)
 assert branch(0x5bf794)==(0xeb,0x6343d8)
 assert branch(0x5bf7c0)==(0xeb,0x6343f0)
 assert w(0x5bf7d8)==0xe784000c
 for va,offset in ((0x586c40,0x1f5d0),(0x586c74,0x1f868),(0x586ca0,0x1fb00)):
  ins=w(va);assert ins&0x0f7f0000==0x051f0000
  slot=va+8+(ins&4095 if ins&0x800000 else -(ins&4095))
  assert w(slot)==offset
 for offset,path,prop in PROPS:print(f'0x020002ce 0x{offset:x} {path} {prop}')
if __name__=='__main__':main()
