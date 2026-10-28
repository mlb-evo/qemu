#!/usr/bin/env python3
"""Verify GTF2 scene-path setter and three named-node initialization calls.

The helper stores a string through an external thunk and sets object+6 bit 1.
This does not prove any DP-to-scene binding or runtime node resolution.
"""
import argparse,struct
from pathlib import Path
BASE=0x100000
WORDS={
 0x6343d8:0xe1a03000,
 0x6343dc:0xe280008c,
 0x6343e0:0xe5d32006,
 0x6343e4:0xe3822002,
 0x6343e8:0xe5c32006,
 0x6343ec:0xeaeb6595,
 0x5c932c:0xe51f1928,
 0x5c933c:0xeb01ac25,
 0x2b6588:0xe51f1314,
 0x2b65a8:0xeb0df78a,
 0x557a28:0xe59f1154,
 0x557a54:0xeb03725f,
}
CALLS={0x5c933c:0x6343d8,0x2b65a8:0x6343d8,0x557a54:0x6343d8}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path)
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 little-endian')
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 for va,expected in WORDS.items():
  got=w(va)
  if got!=expected:raise ValueError(f'0x{va:x}: got 0x{got:08x}, expected 0x{expected:08x}')
 for va,target in CALLS.items():
  ins=w(va);imm=ins&0xffffff
  if imm&0x800000:imm-=0x1000000
  actual=va+8+imm*4
  if actual!=target:raise ValueError(f'BL 0x{va:x} -> 0x{actual:x}, expected 0x{target:x}')
 ins=w(0x6343ec);imm=ins&0xffffff
 if imm&0x800000:imm-=0x1000000
 target=0x6343ec+8+imm*4
 if target!=0x10da48:raise ValueError(f'helper branch -> 0x{target:x}')
 print(f'verified {len(WORDS)} exact ARM words, {len(CALLS)} scene-path calls')
 print('0x6343d8: object+0x06 |= 0x02; delegate string assignment at object+0x8c to 0x10da48')
 print('node-name references are initialization/configuration; DP->scene binding remains unknown')
if __name__=='__main__':main()
