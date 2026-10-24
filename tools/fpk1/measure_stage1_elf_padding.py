#!/usr/bin/env python3
"""Measure decoded zero padding immediately before strict Stage1 ELF starts.

The encoded E0 FF 00 pattern is a distance-one copy token, not a file marker.
Only reports padding and alignment in suffix-local decoded coordinates.
"""
import argparse,json,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

START=0x1318fc
END=0x1f6ffb

def measure(data,at):
    cursor=at
    while cursor>0 and data[cursor-1]==0:
        cursor-=1
    return {"elf_at":hex(at),"zero_padding_before":at-cursor,
            "zero_run_start":hex(cursor),
            "elf_alignment_0x1000":hex(at%0x1000),
            "elf_alignment_0x100":hex(at%0x100),
            "elf_alignment_0x10":hex(at%0x10),
            "prefix_16":data[max(0,at-16):at].hex(),
            "first_16":data[at:at+16].hex()}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous stage1")
        raw=z.read(names[0])
    data,stop,error=decode(raw[0xc2:0xc2+END],START)
    if error or stop!=END:raise ValueError("Unexpected bounded decode failure")
    valid=[e for e in scan_elf(data) if e["strict_elf_valid"]]
    rows=[measure(data,e["at"]) for e in valid]
    out=json.dumps({"start":hex(START),"end":hex(END),"count":len(rows),
                    "results":rows,
                    "warning":"Padding in suffix-local coordinates cannot establish an original imagefs file directory."},indent=2)+"\n"
    print(out,end="")
    if a.json:a.json.write_text(out)
if __name__=="__main__":main()
