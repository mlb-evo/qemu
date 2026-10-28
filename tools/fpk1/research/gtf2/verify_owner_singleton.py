#!/usr/bin/env python3
"""Verify lazy one-time HMI owner initialization in stock GTF2 ARM ELF."""
import argparse,struct
from pathlib import Path
BASE=0x100000
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path)
 a=p.parse_args();b=a.elf.read_bytes()
 assert b[:6]==b'\x7fELF\x01\x01'
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 def bl(va):
  op=w(va)
  if op&0x0f000000!=0x0b000000:return None
  d=op&0xffffff
  if d&0x800000:d-=0x1000000
  return va+8+4*d
 assert w(0x2bae28)==0xe92d4010
 assert w(0x2bae30)==0xe5943000
 assert w(0x2bae34)==0xe3130001
 assert bl(0x2bae40)==0x10e69c
 assert bl(0x2bae50)==0x25ef60
 assert bl(0x2bae58)==0x10f0e0
 assert bl(0x2bae68)==0x10e1d4
 assert w(0x2bae74)==0x00afb38c
 assert w(0x2bae78)==0x00b64040
 assert w(0x2bae7c)==0x002432c8
 assert w(0x2bae80)==0x00a65a90
 assert w(0x25ef60)==0xe92d4ff0
 assert bl(0x222074)==0x2bae28
 assert bl(0x129758)==0x2bae28
 getter=[];ctor=[]
 for va in range(BASE,min(BASE+len(b),0x810000),4):
  dest=bl(va)
  if dest==0x2bae28:getter.append(va)
  if dest==0x25ef60:ctor.append(va)
 assert ctor==[0x2bae50],ctor
 assert len(getter)==21527,len(getter)
 print('HMI owner singleton getter: 0x2bae28, instance 0xb64040, guard 0xafb38c')
 print('acquire 0x10e69c; release 0x10f0e0; destructor registration 0x10e1d4')
 print('constructor 0x25ef60 has one direct caller: 0x2bae50')
 print('getter direct call sites:',len(getter))
 print('other example calls: initialization path 0x222074, DP handler path 0x129758')
 print('Not established: execution ordering versus Kanzi scene load/activation')
if __name__=='__main__':main()
