#!/usr/bin/env python3
"""Resolve GTF2 factory view IDs lacking nearby SV_* strings.

Scans each lazy initializer for direct pointers to its CHMI*ViewData::construct
diagnostic. Uses the first matching pointer within 0x3000 bytes, recording
its address so the result can be checked against disassembly. This is a
bounded heuristic, not a guarantee of C++ type identity.
"""
import argparse
import json
import struct
from pathlib import Path

BASE=0x100000
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    p.add_argument("--window",type=lambda s:int(s,0),default=0x3000)
    args=p.parse_args()
    b=args.elf.read_bytes()
    if b[:6]!=b"\x7fELF\x01\x01":p.error("expected little-endian ELF32")
    def word(a):
        i=a-BASE
        return struct.unpack_from("<I",b,i)[0] if 0<=i<=len(b)-4 else None
    def bl(a):
        x=word(a)
        if x is None or x>>24!=0xeb:return None
        d=x&0xffffff
        if d&0x800000:d-=0x1000000
        return a+8+4*d
    rows=[]
    for key in range(1,180):
        case=word(0x25a968+4*(key-1))
        if case==0x25bd7c:continue
        init=next((bl(a) for a in range(case,case+48,4) if bl(a) is not None),None)
        if init is None:continue
        matches=[]
        for a in range(init,min(init+args.window,0xa634dc),4):
            ptr=word(a)
            if ptr is None or not BASE<=ptr<BASE+len(b):continue
            s=b[ptr-BASE:ptr-BASE+128].split(b"\0")[0].decode("latin1","replace")
            if s.startswith("CHMI") and "ViewData::construct" in s:
                matches.append({"literal_va":hex(a),"string_va":hex(ptr),"name":s})
                break
        rows.append({"id":key,"initializer_va":hex(init),
                     "construct":matches[0] if matches else None})
    print(json.dumps({"supported":len(rows),
                      "construct_diagnostics":sum(r["construct"] is not None for r in rows),
                      "rows":rows},indent=2))
if __name__=="__main__":main()
