#!/usr/bin/env python3
"""Locate direct ARM BL callers of the GTF2 state view-ID accessor and setter."""
import argparse
import json
import struct
from pathlib import Path

BASE=0x100000
TEXT_SIZE=0x9634dc
TARGETS={
    "get_visible_view_id":0x69d820,
    "set_view_id_if_mask_0x6":0x69d810,
    "get_candidate_view_id":0x69d7f0,
    "set_state_flag_0x10":0x69d84c,
}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    args=p.parse_args()
    b=args.elf.read_bytes()
    if b[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little endian")
    result={k:[] for k in TARGETS}
    by_address={v:k for k,v in TARGETS.items()}
    for off in range(0,min(TEXT_SIZE,len(b))-3,4):
        instruction=struct.unpack_from("<I",b,off)[0]
        if (instruction&0x0f000000)!=0x0b000000:
            continue
        immediate=instruction&0xffffff
        if immediate&0x800000:immediate-=0x1000000
        target=BASE+off+8+immediate*4
        if target in by_address:
            result[by_address[target]].append(hex(BASE+off))
    print(json.dumps({k:{"target":hex(TARGETS[k]),"callsites":v,
                         "count":len(v)} for k,v in result.items()},indent=2))
if __name__=="__main__":main()
