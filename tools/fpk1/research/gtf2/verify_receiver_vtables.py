#!/usr/bin/env python3
"""Verify GTF2's indirect receiver attachment interface from stock ELF vtables."""
import argparse,csv,struct,sys
from pathlib import Path
BASE=0x100000

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('elf',type=Path)
 ap.add_argument('--csv',action='store_true')
 args=ap.parse_args();data=args.elf.read_bytes()
 if data[:6]!=b'\x7fELF\x01\x01':ap.error('expected ELF32 little endian')
 word=lambda va:struct.unpack_from('<I',data,va-BASE)[0]
 assert word(0x6218bc)==0xe58010b8
 assert word(0x6218cc)==0xe59000b8
 needle=struct.pack('<I',0x6218b8)
 hits=[];start=0
 while True:
  i=data.find(needle,start)
  if i<0:break
  va=BASE+i;vtable=va-0x30
  if 0x880000<=vtable<0x900000 and all(0x600000<=word(vtable+j)<0x700000 for j in (0,4,8,0x30,0x34)):
   assert word(vtable+0x30)==0x6218b8
   hits.append((f'0x{vtable:x}',f'0x{va:x}',f'0x{word(vtable):x}',f'0x{word(vtable+0x34):x}'))
  start=i+4
 assert len(hits)==63,(len(hits),'expected 63 shared virtual binding slots')
 if args.csv:
  w=csv.writer(sys.stdout);w.writerow(('vtable_va','bind_slot_va','slot0_fn','next_slot_fn'));w.writerows(hits)
 else:
  print(f'{len(hits)} distinct vtables share virtual binding slot +0x30 -> 0x6218b8')
  print('0x6218b8 writes receiver pointer to wrapper+0xb8; 0x6218cc reads it')
  for row in hits[:8]:print(*row)
if __name__=='__main__':main()
