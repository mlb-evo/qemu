#!/usr/bin/env python3
"""Resolve GTF2 view-ID factory cases to embedded SV_* diagnostic names.

Names are taken from strings referenced by each case's lazy initializer;
they are not inferred from external libraries or file names. Some initializers
use indirect wrappers, so a missing name is not evidence of an absent view.
"""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    p.add_argument("--scan-bytes",type=int,default=128)
    args=p.parse_args()
    b=args.elf.read_bytes()
    if b[:6]!=b"\x7fELF\x01\x01":
        p.error("expected little-endian ELF32")
    def w(va):
        off=va-BASE
        return struct.unpack_from("<I",b,off)[0] if 0<=off<=len(b)-4 else None
    def bl(va):
        x=w(va)
        if x is None or x>>24!=0xeb:return None
        d=x&0xffffff
        if d&0x800000:d-=0x1000000
        return va+8+4*d
    rows=[]
    for key in range(1,180):
        case=w(0x25a968+4*(key-1))
        if case==0x25bd7c:continue
        initializer=next((bl(a) for a in range(case,case+48,4) if bl(a)),None)
        if initializer is None:continue
        names=[]
        for va in range(initializer,initializer+args.scan_bytes,4):
            ins=w(va)
            if ins is None or (ins&0x0f7f0000)!=0x051f0000:continue
            lit=va+8+(ins&0xfff)*(1 if ins&0x00800000 else -1)
            ptr=w(lit)
            if ptr is None or not BASE<=ptr<BASE+len(b):continue
            s=b[ptr-BASE:ptr-BASE+160].split(b"\0")[0].decode("latin1","replace")
            if s.startswith("SV_") and s not in names:names.append(s)
        rows.append({"view_id":key,"initializer_va":hex(initializer),
                     "diagnostic_name":names[0] if names else None})
    print(json.dumps({"total_supported":len(rows),
                      "named":sum(x["diagnostic_name"] is not None for x in rows),
                      "rows":rows},indent=2))
if __name__=="__main__":
    main()
