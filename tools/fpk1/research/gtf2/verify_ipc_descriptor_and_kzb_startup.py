#!/usr/bin/env python3
"""Verify stock GTF2 startup KZB resource name and IHmiKss descriptor wiring."""
import argparse,struct
from pathlib import Path
BASE=0x100000
p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
b=a.elf.read_bytes();assert b[:6]==b'\x7fELF\x01\x01'
def w(x):return struct.unpack_from('<I',b,x-BASE)[0]
def bl(x):
 op=w(x);assert op&0x0f000000==0x0b000000,(hex(x),hex(op))
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+d*4
assert w(0x114ce8)==0x7bdeb5
assert b[0x7bdeb5-BASE:0x7bdeb5-BASE+22]==b'DisplaySupervisor.kzb\0'
assert w(0x114a00)==0xe59f12e0
assert bl(0x114a04)==0x141fd8
assert bl(0x141ff4)==0x10e7bc
assert bl(0x142004)==0x141fbc
assert bl(0x114a44)==0x142cec
assert w(0xa7e838)==0x88f55d
assert w(0xa7e83c)==0x88f579
assert b[0x88f55d-BASE:0x88f55d-BASE+28]==b'asi.gss.ipc.rte.hmi.IHmiKss\0'
assert b[0x88f579-BASE:0x88f579-BASE+33]==b'asi.gss.ipc.rte.hmi.IHmiKssReply\0'
assert w(0x50fe8c)==0xa7e838
assert w(0x5107f8)==0xe51f2974
assert w(0x5107fc)==0xe7842003
assert w(0x510804)==0xe3a02001
assert w(0x510808)==0xe7842003
print('Startup 0x114a00 passes DisplaySupervisor.kzb to 0x141fd8 (string setter -> 0x141fbc)')
print('Later startup resource-related call 0x114a44 -> 0x142cec (conditional path)')
print('GTF2 owner constructor 0x5107f8 stores descriptor 0xa7e838 for IHmiKss and IHmiKssReply')
print('No proof yet of KZB activation or actual IPC subscription timing')
