#!/usr/bin/env python3
"""Verify synchronous RTE queue consumer and dequeue in stock GTF2."""
import argparse,struct
p=argparse.ArgumentParser();p.add_argument('elf');a=p.parse_args();b=open(a.elf,'rb').read();base=0x100000
w=lambda x:struct.unpack_from('<I',b,x-base)[0]
def branch(x):
 op=w(x);assert op&0x0e000000==0x0a000000,(hex(x),hex(op));d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+4*d
edges={0x114ab0:0x13d098,0x114ab4:0x14199c,0x114acc:0x13d098,0x114ad0:0x13a614,0x114ad8:0x114ab0,0x141f08:0x13a378,0x141f40:0x13e7b0}
for x,y in edges.items():assert branch(x)==y,(hex(x),hex(branch(x)),hex(y))
ops={0x141eec:0xe594300c,0x141ef0:0xe3530000,0x141ef4:0x0a00000e,0x141ef8:0xe5942004,0x141f0c:0xe5943004,0x141f10:0xe5942010,0x141f14:0xe2833001,0x141f18:0xe5843004,0x141f1c:0xe1530002,0x141f20:0x23a03000,0x141f24:0x25843004,0x141f28:0xe594300c,0x141f2c:0xe2433001,0x141f30:0xe584300c,0x141f34:0xe3a03000,0x141f38:0xe5c43014}
for x,y in ops.items():assert w(x)==y,(hex(x),hex(w(x)),hex(y))
print('PASS: startup 0x114ab4 invokes queue consumer 0x14199c before 0x114ad0 occupancy test')
print('PASS: 0x141eec..0x141f30 destroys front element, advances read index, decrements count')
print('Note: processing may involve virtual calls; no claim of worker thread or IPC subscription completion')
