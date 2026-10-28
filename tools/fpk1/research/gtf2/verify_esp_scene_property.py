#!/usr/bin/env python3
"""Verify TelltaleHMI_Display DP 0x020002cd -> MV_ClusterFull ESP property."""
import argparse,struct
from pathlib import Path
BASE=0x100000
SLOTS={0x293ee8:'MV_ClusterFull.StatusBar.line1_auchEarlyWelcome.ESP',0x293ef0:'ESP'}
WORDS={0x293ef4:0x453b8,0x587544:0x453b8,0x29465c:0xe7840001,0x586bf8:0xe7900003}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args();b=a.elf.read_bytes()
 assert b[:6]==b'\x7fELF\x01\x01'
 def w(a):return struct.unpack_from('<I',b,a-BASE)[0]
 for va,val in WORDS.items():assert w(va)==val,(hex(va),hex(w(va)))
 for slot,s in SLOTS.items():
  addr=w(slot)
  assert b[addr-BASE:addr-BASE+len(s)+1]==s.encode()+b'\0',(hex(slot),hex(addr))
 for va,target in [(0x29461c,0x6343d8),(0x294648,0x6343f0),(0x586bfc,0x6218cc)]:
  ins=w(va);imm=ins&0xffffff
  if imm&0x800000:imm-=0x1000000
  assert ins>>24==0xeb and va+8+4*imm==target,(hex(va),hex(va+8+4*imm))
 for va,slot in [(0x2945fc,0x293ee8),(0x294630,0x293ef0),(0x294658,0x293ef4),(0x586bf4,0x587544)]:
  ins=w(va)
  assert ins&0x0f7f0000==0x051f0000
  actual=va+8+(ins&4095 if ins&0x800000 else -(ins&4095))
  assert actual==slot,(hex(va),hex(actual))
 print('verified DP 0x020002cd -> owner+0x453b8 -> MV_ClusterFull.StatusBar.line1_auchEarlyWelcome.ESP -> ESP')
if __name__=='__main__':main()
