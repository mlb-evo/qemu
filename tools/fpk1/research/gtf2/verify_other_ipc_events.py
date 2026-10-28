#!/usr/bin/env python3
"""Verify two additional GTF2 IPC-to-HMI event paths against original ARM ELF."""
import argparse,struct
from pathlib import Path
BASE=0x100000
WORDS={
0x569150:0xe59f3b74,0x569154:0xe1540003,0x569158:0x0a001055,
0x569ccc:0x020001f7,
0x5753bc:0xe51f3294,0x5753c0:0xe1580003,0x5753c4:0x0a004401,
0x575130:0x02000295,
0x5863d0:0xe51f3e8c,0x5863d4:0xe7943003,
0x5863d8:0xe5d320e3,0x5863dc:0xe3822010,0x5863e0:0xe5c320e3,
0x5863e4:0xe51f3e9c,0x5863e8:0xe7943003,
0x5863ec:0xe5d320e3,0x5863f0:0xe3822002,0x5863f4:0xe5c320e3,
0x56d2b4:0xebf536db,0x56d2c8:0xebffcb82,0x56d2d0:0xe5933070,
}
BRANCHES={0x569158:0x56d2b4,0x5753c4:0x5863d0}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected little-endian ELF32')
 def word(va):return struct.unpack_from('<I',b,va-BASE)[0]
 for va,expected in WORDS.items():
  got=word(va)
  if got!=expected:raise ValueError(f'0x{va:x}: got 0x{got:08x}, expected 0x{expected:08x}')
 for va,dest in BRANCHES.items():
  ins=word(va);imm=ins&0xffffff
  if imm&0x800000:imm-=0x1000000
  actual=va+8+imm*4
  if actual!=dest:raise ValueError(f'branch at 0x{va:x}: 0x{actual:x} != 0x{dest:x}')
 print(f'verified {len(WORDS)} ARM words, {len(BRANCHES)} event-dispatch edges')
 print('RPM DP 0x02000295 -> 0x5863d0 -> two object dirty-bit writes')
 print('Gear DP 0x020001f7 -> 0x56d2b4 -> virtual receiver calls')
if __name__=='__main__':main()
