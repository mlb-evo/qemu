#!/usr/bin/env python3
"""Find ARM direct BL/BLX-immediate references to GTF2 view-switch functions.

These methods are usually reached through vtables, so a zero direct-call
count is expected and must not be interpreted as unreachable code.
"""
import argparse
import json
import struct
from pathlib import Path

BASE=0x100000
TARGETS={
    "BaseViewManager.handleViewSwitch":0x6a91a8,
    "ViewManager.handleViewSwitch":0x11a250,
    "ViewManager.handleViewSwitchCenter":0x118c74,
    "ViewManager.doSwitch":0x119688,
    "provider.getView":0x6a9e9c,
    "view.prepareResources":0x1217c8,
}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    a=p.parse_args()
    data=a.elf.read_bytes()
    if data[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little-endian")
    hits={name:[] for name in TARGETS}
    for off in range(0,0x9634dc-3,4):
        ins=struct.unpack_from("<I",data,off)[0]
        if (ins&0x0f000000)!=0x0b000000:continue
        delta=ins&0xffffff
        if delta&0x800000:delta-=0x1000000
        dest=BASE+off+8+delta*4
        for name,target in TARGETS.items():
            if dest==target:hits[name].append(hex(BASE+off))
    print(json.dumps({name:{"target":hex(TARGETS[name]),"count":len(sites),
                            "callsites":sites} for name,sites in hits.items()},indent=2))
if __name__=="__main__":main()
