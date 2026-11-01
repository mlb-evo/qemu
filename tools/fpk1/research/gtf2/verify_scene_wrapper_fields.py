#!/usr/bin/env python3
import argparse,struct
from pathlib import Path
BASE=0x100000
EXPECTED={0x6218b0:0xe280008c,0x6218b4:0xe12fff1e,0x6218b8:0xe5d03006,0x6218bc:0xe58010b8,0x6218c0:0xe3833040,0x6218c4:0xe5c03006,0x6218c8:0xe12fff1e,0x6218cc:0xe59000b8,0x6218d0:0xe12fff1e,0x6343dc:0xe280008c,0x6343e4:0xe3822002,0x6343e8:0xe5c32006,0x6adbd8:0xebfdcf34,0x11e65c:0xeb140c93}
def main():
 p=argparse.ArgumentParser();p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 for va,expected in EXPECTED.items():
  actual=struct.unpack_from('<I',b,va-BASE)[0]
  if actual!=expected:raise ValueError(f'{va:x}: {actual:08x} != {expected:08x}')
 print('verified',len(EXPECTED),'ARM words: path at +0x8c, target at +0xb8')
if __name__=='__main__':main()
