#!/usr/bin/env python3
"""Evidence-gated join of scene wrapper constructors and HMI receiver uses.

Finds constructor path/property setter pairs, the owner-relative pointer store,
and HMI getter calls through that same owner field. Emits scene/property rows,
but does not claim scene activation or rendered effects.
"""
import argparse,csv,re,struct,sys
from collections import defaultdict
from pathlib import Path
BASE=0x100000
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path)
 p.add_argument('--csv',action='store_true');a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 little-endian')
 def w(x):return struct.unpack_from('<I',b,x-BASE)[0]
 def bl(x,target):
  ins=w(x);v=ins&0xffffff
  if v&0x800000:v-=0x1000000
  return ins>>24==0xeb and x+8+4*v==target
 def lit(x):
  ins=w(x)
  if ins&0x0f7f0000!=0x051f0000:return None
  return x+8+(ins&4095 if ins&0x800000 else -(ins&4095))
 def string(ptr):
  if not BASE<=ptr<BASE+len(b):return None
  raw=b[ptr-BASE:ptr-BASE+220].split(b'\0')[0]
  if not 2<len(raw)<220 or not re.fullmatch(rb'[\x20-\x7e]+',raw):return None
  return raw.decode('ascii')
 owners=defaultdict(list)
 for pc in range(0x200000,0x600000,4):
  if not bl(pc,0x6343d8):continue
  prop_call=next((q for q in range(pc+8,pc+0x80,4) if bl(q,0x6343f0)),None)
  if prop_call is None:continue
  paths=[];props=[]
  for lo,hi,dest in ((pc-0x40,pc,paths),(prop_call-0x38,prop_call,props)):
   for x in range(lo,hi,4):
    slot=lit(x)
    if slot and BASE<=slot<BASE+len(b)-4:
     s=string(w(slot))
     if s:dest.append(s)
  paths=[s for s in paths if '.' in s and len(s)>10]
  if not paths or not props:continue
  path=paths[-1];prop=props[-1]
  # Require exact last path component as property: strong, conservative match.
  if path.rsplit('.',1)[-1]!=prop:continue
  for store in range(prop_call+4,prop_call+0x50,4):
   ins=w(store)
   if ins&0x0ff00ff0!=0x07800000:continue
   reg=ins&15
   for x in range(store-36,store,4):
    if (w(x)>>12)&15!=reg:continue
    slot=lit(x)
    if slot and BASE<=slot<BASE+len(b)-4 and w(slot)<0x100000:
     owners[w(slot)].append((path,prop,pc,prop_call,store))
     break
 rows=[];seen=set()
 for call in range(0x570000,0x590000,4):
  if not bl(call,0x6218cc):continue
  for load in range(call-24,call,4):
   ins=w(load)
   # LDR r0,[rBase,rIndex] for either r0 or r4 base.
   if ins&0x0ff00ff0!=0x07900000:continue
   base=(ins>>16)&15;reg=ins&15;dest=(ins>>12)&15
   if dest!=0 or base not in (0,4):continue
   for x in range(load-20,load,4):
    if (w(x)>>12)&15!=reg:continue
    slot=lit(x)
    if not slot or not BASE<=slot<BASE+len(b)-4:continue
    offset=w(slot)
    if offset not in owners:continue
    for path,prop,pc,nc,store in owners[offset]:
     row=(f'0x{load:x}',f'0x{offset:x}',path.split('.')[0],path,prop,f'0x{pc:x}',f'0x{nc:x}',f'0x{store:x}')
     if row not in seen:rows.append(row);seen.add(row)
    break
 if a.csv:
  wr=csv.writer(sys.stdout);wr.writerow(('hmi_use_va','owner_offset','scene','node_path','property','path_setter_call','property_setter_call','owner_store_va'));wr.writerows(rows)
 else:
  for row in rows:print(' | '.join(row[:5]))
  print(f'{len(rows)} exact scene wrapper uses, {len(set(x[1] for x in rows))} owner offsets')
if __name__=='__main__':main()
