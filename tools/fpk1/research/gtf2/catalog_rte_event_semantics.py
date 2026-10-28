#!/usr/bin/env python3
"""Catalog exact IPC callback provenance for RTE DP -> HMI dispatcher edges.

Semantic tiers: named callback from own diagnostic string; payload field and DP
from ARM instructions; dispatch from literal/CMP/BEQ. A visual effect is NOT
inferred from these facts.
"""
import argparse,csv,re,struct,sys
from pathlib import Path
from scan_rte_dp_writes import scan,BASE,START

def catalog(data):
 def w(a):return struct.unpack_from('<I',data,a-BASE)[0]
 def callback_name(call):
  start=next((x for x in range(call-4,max(START,call-0x800),-4) if w(x)&0xffff4000==0xe92d4000),None)
  if start is None:return 'unidentified'
  end=next((x for x in range(start+4,min(start+0x800,0x6a0000),4) if w(x)&0xffff4000==0xe92d4000),start+0x800)
  for a in range(start,end,4):
   ins=w(a)
   if ins&0x0f7f0000!=0x051f0000:continue
   lit=a+8+(ins&4095 if ins&0x800000 else -(ins&4095))
   if not BASE<=lit<=BASE+len(data)-4:continue
   ptr=w(lit)
   if not 0x88e000<=ptr<0x88f800:continue
   m=re.match(rb'([A-Za-z0-9_]+)\(\): batchLock\(\) failed',data[ptr-BASE:ptr-BASE+160])
   if m:return m.group(1).decode()
  return 'unidentified'
 sources={}
 for call,dp,width,offset,_ in scan(data):
  sources.setdefault(int(dp,16),[]).append((callback_name(int(call,16)),width,offset,call))
 for va in range(0x570000,0x580000,4):
  ins=w(va)
  if ins&0x0f7f0000!=0x051f0000:continue
  lit=va+8+(ins&4095 if ins&0x800000 else -(ins&4095))
  if not BASE<=lit<=BASE+len(data)-4:continue
  dp=w(lit)
  if dp not in sources:continue
  for cmpva in (va+4,va+8):
   if w(cmpva)&0x0ff0f000!=0x01500000:continue
   branch=w(cmpva+4)
   if branch>>28!=0 or branch&0x0f000000!=0x0a000000:continue
   d=branch&0xffffff
   if d&0x800000:d-=0x1000000
   target=cmpva+12+4*d
   for name,width,off,call in sources[dp]:
    yield dict(dp_id=f'0x{dp:08x}',callback=name,payload_width=width,payload_offset=off,write_va=call,cmp_va=f'0x{cmpva:x}',handler_va=f'0x{target:x}',source_proof='diagnostic-string' if name!='unidentified' else 'unnamed',visual_effect='unresolved')
   break

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);p.add_argument('--csv',action='store_true');a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected little-endian ELF32')
 rows=list(catalog(b))
 if a.csv:
  wr=csv.DictWriter(sys.stdout,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
 else:
  for r in rows:print(f"{r['dp_id']} {r['callback']:<28} {r['payload_width']} {r['payload_offset']:>4} -> {r['handler_va']}")
  print(f'TOTAL {len(rows)} source-to-dispatch routes; {sum(r["source_proof"]=="diagnostic-string" for r in rows)} named')
if __name__=='__main__':main()
