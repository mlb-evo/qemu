#!/usr/bin/env python3
"""Recover verified RTE DP -> HMI event dispatch edges from GTF2 ARM code.

Requires LDR literal of a DP ID written by an RTE callback, CMP against the
event ID, and BEQ to a handler. This proves dispatch, not visual rendering.
"""
import argparse,csv,struct,sys
from pathlib import Path
from scan_rte_dp_writes import scan,BASE

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path)
 p.add_argument("--csv",action="store_true")
 a=p.parse_args();data=a.elf.read_bytes()
 if data[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little-endian")
 def word(va):return struct.unpack_from("<I",data,va-BASE)[0]
 writers={int(dp,16):(call,width,offset) for call,dp,width,offset,_ in scan(data)}
 rows=[]
 for va in range(0x570000,0x580000,4):
  ins=word(va)
  if ins&0x0f7f0000!=0x051f0000:continue
  literal=va+8+(ins&4095 if ins&0x800000 else -(ins&4095))
  if not BASE<=literal<=BASE+len(data)-4:continue
  dp=word(literal)
  if dp not in writers:continue
  for cmp_va in (va+4,va+8):
   if word(cmp_va)&0x0ff0f000!=0x01500000:continue
   branch_va=cmp_va+4;branch=word(branch_va)
   if branch>>28!=0 or branch&0x0f000000!=0x0a000000:continue
   delta=branch&0xffffff
   if delta&0x800000:delta-=0x1000000
   target=branch_va+8+delta*4
   call,width,offset=writers[dp]
   rows.append((f"0x{dp:08x}",call,width,offset,
                f"0x{cmp_va:08x}",f"0x{branch_va:08x}",f"0x{target:08x}"))
   break
 if a.csv:
  writer=csv.writer(sys.stdout)
  writer.writerow(("dp_id","writer_va","payload_width","payload_offset",
                   "cmp_va","beq_va","handler_va"))
  writer.writerows(rows)
 else:
  for row in rows:print(" ".join(row))
  print(f"TOTAL {len(rows)} verified dispatch edges")
if __name__=="__main__":main()
