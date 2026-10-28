#!/usr/bin/env python3
"""Verify two RTE event fan-outs by exact ARM dataflow, without naming UI widgets."""
import argparse,struct
from pathlib import Path
BASE=0x100000
EVENTS=[
 dict(name='HMI_EngineID_MKB',dp=0x02000225,literal=0x574fcc,cmp=0x574020,branch=0x574024,target=0x584710,receivers=(0x4b02c,0x51310),slot_literals=(0x583928,0x58392c),calls=(0x584750,0x584794)),
 dict(name='RTE field at 0x694b5c',dp=0x020001e6,literal=0x5750c4,cmp=0x574bbc,branch=0x574bc0,target=0x5812a8,receivers=(0x1f5d0,0x1fb00),slot_literals=(0x581b84,0x581b88),calls=(0x5812d8,0x581304)),
]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected little-endian ELF32')
 def w(x):return struct.unpack_from('<I',b,x-BASE)[0]
 def check(x,v):
  got=w(x)
  if got!=v:raise ValueError(f'0x{x:x}: expected 0x{v:08x}, got 0x{got:08x}')
 for e in EVENTS:
  check(e['literal'],e['dp']);check(e['cmp'],0xe1580003)
  ins=w(e['branch'])
  if ins>>24!=0x0a:raise ValueError(f"0x{e['branch']:x}: expected BEQ")
  d=ins&0xffffff
  if d&0x800000:d-=0x1000000
  if e['branch']+8+d*4!=e['target']:raise ValueError(f"0x{e['branch']:x}: unexpected branch target")
  for va,offset in zip(e['slot_literals'],e['receivers']):check(va,offset)
  for va in e['calls']:check(va,0xe12fff3b if e['dp']==0x02000225 else 0xe12fff3c)
  for va in ((0x58473c,0x584780) if e['dp']==0x02000225 else (0x5812c8,0x5812f4)):
   check(va,0xe3a03002)
  print(f"{e['name']} DP 0x{e['dp']:08x} -> 0x{e['target']:x}: two distinct receiver slots, two virtual calls, kind 2")
if __name__=='__main__':main()
