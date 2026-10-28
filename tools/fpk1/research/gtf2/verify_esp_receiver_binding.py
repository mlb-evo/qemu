#!/usr/bin/env python3
"""Verify ESP receiver attachment during GTF2 owner construction (stock ARM ELF).

The constructor uses a virtual +0x30 call to attach a receiver subobject.
Addresses are original GTF2 VAs (ELF32 little endian, load base 0x100000).
"""
import argparse,struct
from pathlib import Path
BASE=0x100000
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('elf',type=Path)
 a=p.parse_args();b=a.elf.read_bytes()
 assert b[:6]==b'\x7fELF\x01\x01'
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 expected={
  0x29465c:0xe7840001, # str r0,[r4,r1] (owner field)
  0x294660:0xe51f1708, # ldr r1,[pc,#-0x708] (descriptor pointer)
  0x294664:0xeb0e6d7d, # bl 0x62fc60 (descriptor virtual +0x3c)
  0x294670:0xe7943008, # ldr r3,[r4,r8] (ESP wrapper)
  0x294698:0xe5933000, # ldr r3,[r3] (vtable)
  0x29469c:0xe2811004, # add r1,r1,#4
  0x2946a0:0xe0841001, # add r1,r4,r1 (embedded receiver)
  0x2946b4:0xe5933030, # ldr r3,[r3,#0x30]
  0x2946dc:0xe12fff33, # blx r3 (llvm-objdump may show unknown)
  0x6218bc:0xe58010b8, # str r1,[r0,#0xb8]
  0x6218cc:0xe59000b8, # ldr r0,[r0,#0xb8]
 }
 for va,opcode in expected.items():
  assert w(va)==opcode,(hex(va),hex(w(va)),hex(opcode))
 assert w(0x293ed0)==0x45368
 assert w(0x293ef4)==0x453b8
 assert w(0x293ef8)==0x45644
 assert w(0x293f60)==0x874100
 assert w(0x293ed0)+0x50==w(0x293ef4)
 assert w(0x293ef8)+4==0x45648
 # Virtual +0x30 method is common to 63 wrapper vtables; method writes receiver pointer.
 needle=struct.pack('<I',0x6218b8);occ=b.count(needle)
 assert occ==63,(occ,'expected common binding method pointer in 63 tables')
 print('ESP wrapper owner offset: 0x453b8')
 print('ESP receiver subobject owner offset: 0x45648')
 print('ESP constructor: descriptor call at 0x294664, binder BLX at 0x2946dc')
 print('Binding method +0x30 -> 0x6218b8 stores owner+0x45648 at wrapper+0xb8')
 print('Verified: 63 vtables share binder method pointer')
 print('Not proved: when the owner constructor runs relative to Kanzi scene activation')
if __name__=='__main__':main()
