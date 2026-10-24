#!/usr/bin/env python3
"""Analyze ELF alignment and zero-run boundaries in decoded Stage1 LZF suffix."""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

def analyze(data):
    valid=[e for e in scan_elf(data) if e["strict_elf_valid"]]
    rows=[]
    for i,e in enumerate(valid):
        at=e["at"]; phoff=struct.unpack_from("<I",data,at+28)[0]
        n=struct.unpack_from("<H",data,at+44)[0]
        ends=[]
        for j in range(n):
            p=struct.unpack_from("<IIIIIIII",data,at+phoff+32*j)
            if p[0] in (1,2,3,4,6,7):ends.append(at+p[1]+p[4])
        end=max(ends,default=at+52)
        z=at
        while z>0 and data[z-1]==0:z-=1
        prev=rows[-1] if rows else None
        rows.append({"elf":hex(at),"offset_mod_4096":at%4096,
                     "zero_start":hex(z),"zero_length":at-z,
                     "zero_start_mod_4096":z%4096,
                     "inferred_file_end":hex(end),
                     "inferred_end_mod_4096":end%4096,
                     "prev_end_to_zero_start":z-int(prev["inferred_file_end"],16) if prev else None,
                     "previous_elf_delta":at-int(prev["elf"],16) if prev else None})
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        m=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(m)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(m[0])
    decoded,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    rows=analyze(decoded)
    result={"count":len(rows),"rows":rows,"warning":"Inferred PHDR ends exclude section tables/other content; decoded suffix coordinate origin is unknown."}
    t=json.dumps(result,indent=2)+"\n";print(t,end="")
    if a.json:a.json.write_text(t)
if __name__=="__main__":main()
