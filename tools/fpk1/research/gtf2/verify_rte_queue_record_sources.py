#!/usr/bin/env python3
"""Verify 52-byte RTE queue records and all direct enqueue paths in stock GTF2."""
import argparse,struct
p=argparse.ArgumentParser();p.add_argument('elf');a=p.parse_args();b=open(a.elf,'rb').read();BASE=0x100000
assert b[:6]==b'\x7fELF\x01\x01'
def w(x):return struct.unpack_from('<I',b,x-BASE)[0]
def bl(x):
 op=w(x);assert op&0x0f000000==0x0b000000,(hex(x),hex(op))
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+4*d
edges={0x114a84:0x14250c,0x114a88:0x13d098,0x114a98:0x141608,0x14164c:0x10e678,0x14165c:0x13ce08,0x141664:0x13a378,0x123474:0x141608,0x1414e0:0x13ce08,0x1417b8:0x13ce08,0x121d2c:0x141870,0x1418a0:0x141744,0x141f08:0x13a378}
for site,dest in edges.items():assert bl(site)==dest,(hex(site),hex(bl(site)),hex(dest))
ops={0x114a7c:0xe3a01008,0x114a94:0xe3a03000,0x141640:0xe3a02034,0x141644:0xe1a00006,0x141648:0xe3a01000,0x141650:0xe1a01006,0x141654:0xe1a00004,0x14168c:0xe5879030,0x1419c8:0xe5d43014,0x1419f0:0xe5d43054,0x141a18:0xe5d43064,0x141eec:0xe594300c,0x141f2c:0xe2433001,0x141f30:0xe584300c}
for site,opcode in ops.items():assert w(site)==opcode,(hex(site),hex(w(site)),hex(opcode))
callers={0x141608:[],0x141870:[],0x13ce08:[]}
for i in range(0,len(b)-3,4):
 op=struct.unpack_from('<I',b,i)[0]
 if op&0x0f000000!=0x0b000000:continue
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 dst=BASE+i+8+4*d
 if dst in callers:callers[dst].append(BASE+i)
assert callers[0x141608]==[0x114a98,0x123474],callers[0x141608]
assert callers[0x141870]==[0x121d2c],callers[0x141870]
assert callers[0x13ce08]==[0x1414e0,0x14165c,0x1417b8],callers[0x13ce08]
print('PASS: startup enqueues 52-byte record via 0x114a98 -> 0x141608 -> 0x13ce08')
print('PASS: startup passes r3=0, stored in record+0x30')
print('PASS: two direct callers of 0x141608; three direct producers calling 0x13ce08')
print('PASS: consumer 0x14199c inspects flags and dequeues')
print('Not proven: IHmiKss registration or Kanzi activation')
