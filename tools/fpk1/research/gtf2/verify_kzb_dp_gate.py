#!/usr/bin/env python3
"""Verify startup KZB configuration has a DP-gated optional branch."""
import argparse,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('elf',type=Path);a=p.parse_args();b=a.elf.read_bytes()
BASE=0x100000
def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
def branch(va):
 op=w(va);assert op&0x0e000000==0x0a000000,(hex(va),hex(op))
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return va+8+d*4
for x,y in {0x1149f0:0x1427cc,0x114a04:0x141fd8,0x114a18:0x69ed40,0x114a20:0x114a54,0x114a44:0x142cec,0x114a50:0x114a70,0x114a84:0x14250c,0x114a88:0x13d098,0x114a98:0x141608,0x114aa0:0x689840,0x114ab4:0x14199c}.items():assert branch(x)==y,(hex(x),hex(branch(x)),hex(y))
for x,y in {0x114a00:0xe59f12e0,0x114a08:0xe59f02dc,0x114a0c:0xe1a01006,0x114a10:0xe3a02040,0x114a14:0xe3a03000,0x114a1c:0xe3500001,0x114a3c:0xe3a01000,0x114a40:0xe1a02007,0x114a94:0xe3a03000,0x689840:0xe28000a4}.items():assert w(x)==y,(hex(x),hex(w(x)),hex(y))
assert w(0x114ce8)==0x7bdeb5
assert b[0x7bdeb5-BASE:0x7bdeb5-BASE+22]==b'DisplaySupervisor.kzb\0'
assert w(0x114cec)==0x064004d3
assert b[w(0x69ede8)-BASE:w(0x69ede8)-BASE+9]==b'DP ERROR\0'
for x,y in {0x69ed68:0x6a0a9c,0x69ed90:0x6a187c,0x69eda4:0x6a1b80,0x69edb4:0x6a1750}.items():assert branch(x)==y
print('PASS: startup configures DisplaySupervisor.kzb, then queries DP 0x064004d3 via 0x69ed40')
print('PASS: return == 1 invokes optional 0x142cec; otherwise diagnostic branch')
print('PASS: both branches converge before graphics queue startup work 0x114a98')
print('No evidence this DP query itself loads the KZB or subscribes IHmiKss.')
