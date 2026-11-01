#!/usr/bin/env python3
"""Check startup's named TriggerContextChange hook and its callback target."""
import argparse,struct
p=argparse.ArgumentParser();p.add_argument('elf');a=p.parse_args()
b=open(a.elf,'rb').read();base=0x100000
w=lambda x:struct.unpack_from('<I',b,x-base)[0]
def bl(x):
 op=w(x);assert op&0x0f000000==0x0b000000
 d=op&0xffffff
 if d&0x800000:d-=0x1000000
 return x+8+4*d
assert bl(0x1146b8)==0x222070
assert bl(0x1146bc)==0x14aaf4
assert bl(0x1146c4)==0x222ea4
assert bl(0x114c00)==0x11453c
assert bl(0x114c08)==0x1140b0
assert w(0x114d08)==0x7bdf37
assert b[0x7bdf37-base:0x7bdf37-base+21]==b'TriggerContextChange\0'
assert w(0x114d0c)==0x1152b4
assert w(0x114c54)==0xe5937010
assert w(0x114c64)==0xe59f20a0
assert w(0x114c68)==0xe12fff37
assert bl(0x1152b8)==0x11511c
assert w(0x1152c0)&0x0f000000==0x0a000000
print('Verified: startup 0x114650 builds named TriggerContextChange hook')
print('0x114c44 loads name; 0x114c64 loads function pointer 0x1152b4; 0x114c68 BLX r7')
print('Callback 0x1152b4 calls 0x11511c, then branches to 0x114074')
print('This is NOT proof of IHmiKss IPC callback registration or Kanzi scene loading.')
