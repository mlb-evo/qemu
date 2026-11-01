#!/usr/bin/env python3
"""Verify startup KZB filename is stored in a configuration object, not opened by these helpers."""
import argparse,struct
p=argparse.ArgumentParser();p.add_argument('elf');a=p.parse_args();b=open(a.elf,'rb').read();B=0x100000
w=lambda x:struct.unpack_from('<I',b,x-B)[0]
def branch(x):
 op=w(x);assert op&0x0f000000==0x0b000000,(hex(x),hex(op));d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+d*4
for x,y in {0x114a04:0x141fd8,0x141ff4:0x10e7bc,0x142004:0x141fbc,0x141fc8:0x10f26c,0x142d0c:0x142934,0x142d1c:0x142c04,0x142d2c:0x142b30,0x114a44:0x142cec}.items():assert branch(x)==y,(hex(x),hex(branch(x)),hex(y))
for x,y in {0x141fc4:0xe2800004,0x141fcc:0xe3a03000,0x141fd0:0xe5c43000,0x142d20:0xe1a0100d,0x142d24:0xe2860054,0x142d40:0xe3a03000,0x142d44:0xe5c63000}.items():assert w(x)==y,(hex(x),hex(w(x)),hex(y))
assert w(0x114ce8)==0x7bdeb5
assert b[0x7bdeb5-B:0x7bdeb5-B+22]==b'DisplaySupervisor.kzb\0'
print('PASS: DisplaySupervisor.kzb passed to string setter 0x141fd8 -> 0x141fbc')
print('PASS: setter writes object+4 string, clears object+0 state byte')
print('PASS: 0x142cec constructs data for object+0x54 and clears object+0 state byte')
print('No claim of resource load, scene activation or IPC registration from these functions')
