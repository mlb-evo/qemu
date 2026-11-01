#!/usr/bin/env python3
"""Scan ARM DP dispatches using arithmetic on PC-relative literal values.

The result is a static candidate inventory. It does not establish scene
properties or runtime reachability across conditional branches.
"""
import argparse,csv,struct,sys
from pathlib import Path
BASE=0x100000
def imm(ins):
 v=ins&255;r=((ins>>8)&15)*2
 return ((v>>r)|(v<<(32-r)))&0xffffffff if r else v
def dest(va,ins):
 x=ins&0xffffff
 if x&0x800000:x-=0x1000000
 return va+8+4*x
def scan(b):
 w=lambda va:struct.unpack_from('<I',b,va-BASE)[0]
 seen=set()
 for a in range(0x570000,0x577000,4):
  ins=w(a)
  if ins&0x0f7f0000!=0x051f0000 or (ins>>12)&15!=3:continue
  slot=a+8+(ins&4095 if ins&0x800000 else -(ins&4095))
  if not BASE<=slot<BASE+len(b)-4:continue
  base=w(slot)
  if not 0x02000000<=base<=0x02000400:continue
  value=base;changed=False
  for j in range(1,8):
   q=a+j*4;op=w(q)
   if op&0x0ffff000==0x02433000:
    value=(value-imm(op))&0xffffffff;changed=True
   elif op&0x0ffff000==0x02833000:
    value=(value+imm(op))&0xffffffff;changed=True
   elif op==0xe1580003 and changed:
    nxt=w(q+4)
    if nxt>>24==0x0a:t=dest(q+4,nxt)
    elif nxt>>24==0x1a and w(q+8)>>24==0xea:t=dest(q+8,w(q+8))
    else:continue
    if not 0x570000<=t<0x600000:continue
    key=(value,q,t)
    if key in seen:continue
    seen.add(key)
    yield dict(dp_id=f'0x{value:08x}',base_dp=f'0x{base:08x}',
               cmp_va=f'0x{q:x}',handler_va=f'0x{t:x}',
               scene='unknown',node='unknown',property='unknown')
   elif op>>24 in (0xea,0xeb):break
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('elf',type=Path)
 p.add_argument('--dp-ids',type=Path,help='newline-separated RTE DP IDs to filter')
 p.add_argument('--csv',action='store_true')
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 LE')
 rows=list(scan(b))
 if a.dp_ids:
  ids={int(s,0) for s in a.dp_ids.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')}
  rows=[r for r in rows if int(r['dp_id'],16) in ids]
 if a.csv:
  writer=csv.DictWriter(sys.stdout,fieldnames=list(rows[0]))
  writer.writeheader();writer.writerows(rows)
 else:
  for r in rows:print(r['dp_id'],r['cmp_va'],r['handler_va'])
  print(f'{len(rows)} computed routes; scene properties require separate proof')
if __name__=='__main__':main()
