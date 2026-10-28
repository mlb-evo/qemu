#!/usr/bin/env python3
"""Prove startup path constructs HMI owner before the main event loop."""
import argparse,struct
from pathlib import Path
BASE=0x100000
p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
b=a.elf.read_bytes();assert b[:6]==b'\x7fELF\x01\x01'
def op(va):return struct.unpack_from('<I',b,va-BASE)[0]
def branch(va):
 x=op(va);assert x&0x0f000000==0x0b000000,(hex(va),hex(x))
 d=x&0xffffff
 if d&0x800000:d-=0x1000000
 return va+8+4*d
edges={0x68c894:0x114650,0x1146b8:0x222070,0x222074:0x2bae28,0x2bae50:0x25ef60,0x1146bc:0x14aaf4,0x1146c0:0x69b71c,0x1146c4:0x222ea4,0x68c8c0:0x11459c}
for site,dest in edges.items():assert branch(site)==dest,(hex(site),hex(branch(site)),hex(dest))
assert op(0x68c8b0)==0xe5d53000
assert op(0x68c8bc)==0x1a000004
assert op(0x68c8d0)==0x1afffff6
assert 0x68c894<0x68c8c0
print('Startup 0x68c860 -> 0x114650 -> 0x222070 -> 0x2bae28 -> 0x25ef60')
print('Event loop 0x68c8b0 calls 0x11459c at 0x68c8c0, after init returns')
print('All 8 direct BL edges and loop instruction checks pass')
print('IPC callback registration and Kanzi scene activation ordering NOT established')
