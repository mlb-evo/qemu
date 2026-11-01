#!/usr/bin/env python3
"""Verify RTE startup wait checks a queue count, not a readiness flag."""
import argparse,struct
p=argparse.ArgumentParser();p.add_argument('elf');a=p.parse_args();b=open(a.elf,'rb').read();base=0x100000
w=lambda x:struct.unpack_from('<I',b,x-base)[0]
def branch(x):
 op=w(x);assert op&0x0e000000==0x0a000000,(hex(x),hex(op));d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+4*d
checks={0x114acc:0x13d098,0x114ad0:0x13a614,0x114ad8:0x114ab0,0x13d0b8:0x13cf58,0x13cf94:0x13ce74,0x13ce2c:0x13ccac,0x13ce44:0x13c9c4,0x114a98:0x141608,0x14165c:0x13ce08}
for x,y in checks.items():assert branch(x)==y,(hex(x),hex(branch(x)),hex(y))
ops={0x13a63c:0xe594000c,0x13ce94:0xe580300c,0x13cefc:0xe596300c,0x13cf08:0xe584300c,0x13ce54:0xe594200c,0x13ce60:0xe2823001,0x13ce64:0xe584300c,0x13ce18:0xe590200c,0x13ce1c:0xe2413001,0x13ce20:0xe1520003,0x13ce50:0xe2833001,0x13ce5c:0xe5843008,0x13ce68:0x03a03000,0x13ce6c:0x05843008,0x13d0cc:0x00ab6114}
for x,y in ops.items():assert w(x)==y,(hex(x),hex(w(x)),hex(y))
assert b[0x7bdefa-base:0x7bdefa-base+18]==b'%dms waited on RTE'
print('PASS: RTE wait checks [queue+0xc] count; 0x13ce08 increments count on enqueue')
print('Queue singleton 0x13d098 at global pointer 0xab6114; initialized by 0x13cf58')
print('Not established: which consumers decrement the queue or IPC subscription readiness')
