#!/usr/bin/env python3
"""Export stock IHmiKss IPC callback -> DP ID table from original GTF2 ELF.

No fabricated IPC field names: only offset and ARM load width are recovered.
"""
import argparse,csv,re,struct
from pathlib import Path
BASE=0x100000
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('elf',type=Path);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('ELF32 little-endian required')
 def w(x):return struct.unpack_from('<I',b,x-BASE)[0]
 def target(va,ins):
  v=ins&0xffffff
  if v&0x800000:v-=0x1000000
  return va+8+v*4
 def callback(call):
  start=next((x for x in range(call-4,max(0x680000,call-0x800),-4) if w(x)&0xffff4000==0xe92d4000),None)
  if start is None:return 'unknown'
  end=next((x for x in range(start+4,min(start+0x800,0x6a0000),4) if w(x)&0xffff4000==0xe92d4000),start+0x800)
  for x in range(start,end,4):
   ins=w(x)
   if ins&0x0f7f0000!=0x051f0000:continue
   lit=x+8+(ins&4095 if ins&0x800000 else -(ins&4095))
   if not BASE<=lit<BASE+len(b)-4:continue
   ptr=w(lit)
   if not 0x88e000<=ptr<0x88f800:continue
   m=re.match(rb'([A-Za-z0-9_]+)\(\): batchLock\(\) failed',b[ptr-BASE:ptr-BASE+160])
   if m:return m.group(1).decode()
  return 'unknown'
 rows=[]
 for call in range(0x680000,0x6a0000,4):
  ins=w(call)
  if ins&0x0f000000!=0x0b000000 or target(call,ins)!=0x131390:continue
  for back in (8,12,16):
   x=call-back;li=w(x)
   if li&0x0f7f0000!=0x051f0000 or (li>>12)&15!=1:continue
   slot=x+8+(li&4095 if li&0x800000 else -(li&4095))
   if not BASE<=slot<BASE+len(b)-4:continue
   dp=w(slot)
   if dp>>24!=2:continue
   for q in range(x+4,call,4):
    op=w(q)
    if op&0x0ff00000==0x05d00000 and (op>>12)&15==2:width='u8';offset=op&4095
    elif op&0x0ff000f0==0x01d000b0 and (op>>12)&15==2:width='u16';offset=(op&15)|((op>>4)&240)
    else:continue
    rows.append(dict(ipc_interface='asi.gss.ipc.rte.hmi.IHmiKss',callback=callback(call),
       field_name='unknown (binary offset only)',ipc_field_offset=f'0x{offset:x}',
       field_read_type=width,dp_id=f'0x{dp:08x}',dp_write_call_va=f'0x{call:x}',
       evidence='ARM callback load + DP literal + BL 0x131390'))
    break
   break
 rows.sort(key=lambda r:(r['callback'],r['dp_id']))
 assert len(rows)==176 and len({r['dp_id'] for r in rows})==176,(len(rows),'expected 176 unique DP IDs')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 print(f'Exported {len(rows)} IPC-to-DP mappings to {a.output}')
if __name__=='__main__':main()
