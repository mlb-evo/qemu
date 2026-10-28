#!/usr/bin/env python3
"""Verify the event->queue->record->view static control/dataflow anchors in GTF2.

Does not infer runtime order of visible screens; checks fixed ARM BL and
vtable-pointer evidence against an original, unmodified ELF32 image.
"""
import argparse
import json
import struct
from pathlib import Path

BASE=0x100000
EDGES=[
    (0x6a9894,0x69d4c8,"BaseViewManager event -> queue drain"),
    (0x69d50c,0x69d19c,"queue drain -> record event"),
    (0x69d22c,0x6ac3f8,"record event -> classifier"),
    (0x69d298,0x69cbf0,"record event -> chain wrapper"),
    (0x69cca8,0x69c68c,"chain wrapper -> sync"),
    (0x69c8f8,0x69d810,"sync -> conditional ID setter"),
    (0x6a8ee4,0x69d3d4,"manager phase -> record notification"),
    (0x6a9380,0x69d42c,"manager pending queue -> drain"),
    (0x6a9048,0x69d5dc,"manager phase-one -> drain"),
]
VTABLE=[(0x7bfaf0+0x2c,0x11a8bc,"derived event callback"),
        (0x7bfaf0+0x50,0x11a250,"derived view switch"),
        (0x7bfaf0+0x58,0x11871c,"derived view selector"),
        (0x891958+0x2c,0x6a96d0,"base event callback"),
        (0x891958+0x50,0x6a91a8,"base view switch")]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("elf",type=Path)
 args=p.parse_args()
 b=args.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little endian")
 def word(va):return struct.unpack_from("<I",b,va-BASE)[0]
 rows=[]
 for site,target,label in EDGES:
  ins=word(site);delta=ins&0xffffff
  if delta&0x800000:delta-=0x1000000
  observed=site+8+delta*4
  valid=ins&0x0f000000==0x0b000000 and observed==target
  rows.append({"kind":"BL","site":hex(site),"target":hex(target),
               "observed":hex(observed),"label":label,"ok":valid})
 for site,target,label in VTABLE:
  observed=word(site)
  rows.append({"kind":"vtable","site":hex(site),"target":hex(target),
               "observed":hex(observed),"label":label,"ok":observed==target})
 print(json.dumps(rows,indent=2))
 if not all(row["ok"] for row in rows):raise SystemExit(1)
if __name__=="__main__":main()
