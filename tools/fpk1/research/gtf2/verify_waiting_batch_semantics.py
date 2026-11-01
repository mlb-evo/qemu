#!/usr/bin/env python3
"""Prove startup-drained queue processes image/texture batches, not IPC subscriptions."""
import argparse,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('elf',type=Path);a=p.parse_args()
b=a.elf.read_bytes();BASE=0x100000
assert b[:6]==b'\x7fELF\x01\x01'
def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
def branch(va):
 op=w(va);assert op&0x0e000000==0x0a000000
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return va+8+4*d
strings={0x141f84:b'handleWaitingBatch()',0x141f88:b'batchInFlight',0x141f8c:b'mergeFinished',0x141f90:b'imagesLoaded',0x141f94:b'imageIdsWaitFor',0x141f9c:b"handleWaitingBatch(), image %s couldn't be loaded",0x141fa0:b"handleWaitingBatch(), texture %s couldn't be created",0x141fa4:b"handleWaitingBatch(), texture %s couldn't be created from atlas",0x141fac:b'handleWaitingBatch() %d textures created',0x141fb0:b'handleWaitingBatch(), batch completed, completionID = %d'}
for literal,s in strings.items():
 ptr=w(literal)
 assert b[ptr-BASE:ptr-BASE+len(s)+1]==s+b'\0',(hex(literal),s)
for va,opcode in {0x141ac4:0xe5963000,0x141ac8:0xe593300c,0x141acc:0xe12fff33,0x141c78:0xe5963000,0x141c80:0xe593300c,0x141c84:0xe12fff33,0x141cf4:0xe5963000,0x141cf8:0xe593300c,0x141cfc:0xe12fff33,0x141eec:0xe594300c,0x141f2c:0xe2433001,0x141f30:0xe584300c}.items():assert w(va)==opcode
for site,dest in {0x114ab4:0x14199c,0x141b24:0x10e264,0x141cb8:0x10e264,0x141d30:0x10e264,0x141e2c:0x10e264,0x141eb8:0x10e264}.items():assert branch(site)==dest
assert b[w(0x114cf4)-BASE:w(0x114cf4)-BASE+18]==b'%dms waited on RTE'
print('PASS: startup invokes image/texture handleWaitingBatch at 0x14199c')
print('PASS: 10 embedded image/texture/completion diagnostics and three virtual +0xc calls')
print('This queue is NOT evidence of IHmiKss IPC subscription.')
