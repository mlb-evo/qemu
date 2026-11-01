#!/usr/bin/env python3
"""Verify GTF2 startup RTE wait loop and elapsed-time diagnostic."""
import argparse,struct
from pathlib import Path
BASE=0x100000
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('elf',type=Path)
a=p.parse_args();b=a.elf.read_bytes()
assert b[:6]==b'\x7fELF\x01\x01'
def w(x):return struct.unpack_from('<I',b,x-BASE)[0]
def target(x):
 op=w(x); assert op&0x0e000000==0x0a000000
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+d*4
assert target(0x114ab0)==0x13d098
assert target(0x114ab4)==0x14199c
assert target(0x114ac8)==0x10dcc4
assert target(0x114acc)==0x13d098
assert target(0x114ad0)==0x13a614
assert target(0x114ad8)==0x114ab0
assert target(0x114b1c)==0x10e264
assert w(0x114ad4)==0xe3500000
assert w(0x13a63c)==0xe594000c
assert w(0x13a640)==0xe2500000
assert w(0x13a644)==0x13a00001
assert w(0x114ac0)==0xe3a00002
assert w(0x114ac4)==0xe3a01000
assert w(0x114cf4)==0x7bdefa
s=b[0x7bdefa-BASE:0x7bdefa-BASE+24].split(b'\0')[0]
assert s==b'%dms waited on RTE',s
print('RTE startup wait: 0x114ab0..0x114ad8, loops while [RTE object+0xc] != 0')
print('Body calls 0x13d098, 0x14199c, 0x10dcc4(2,0)')
print('Elapsed-time diagnostic: "%dms waited on RTE" at 0x7bdefa')
print('NOT proved: IPC subscription readiness or Kanzi scene activation')
