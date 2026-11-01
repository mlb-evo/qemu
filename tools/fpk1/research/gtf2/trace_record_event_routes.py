#!/usr/bin/env python3
"""Scan original GTF2 ARM PT_LOAD for direct callers of view-record event routes."""
import argparse,json,struct
from pathlib import Path
BASE=0x100000
TARGETS={
"record_event_dispatch":0x69d19c,
"record_event_action":0x69cbf0,
"record_event_wrapper":0x69d0cc,
"record_chain_sync":0x69c68c,
"record_selection_set":0x69c64c,
"record_index_lookup":0x6ac100,
"record_event_classify":0x6ac3f8,
}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("elf",type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("ELF32 little endian required")
 hits={name:[] for name in TARGETS};lookup={v:k for k,v in TARGETS.items()}
 for off in range(0,min(0x9634dc,len(b))-3,4):
  ins=struct.unpack_from("<I",b,off)[0]
  if ins&0x0f000000!=0x0b000000:continue
  delta=ins&0xffffff
  if delta&0x800000:delta-=0x1000000
  dest=BASE+off+8+4*delta
  if dest in lookup:hits[lookup[dest]].append(hex(BASE+off))
 print(json.dumps({name:{"address":hex(addr),"direct_bl":hits[name]} for name,addr in TARGETS.items()},indent=2))
if __name__=="__main__":main()
