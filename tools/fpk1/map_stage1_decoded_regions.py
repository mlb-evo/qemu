#!/usr/bin/env python3
"""Summarize reconstructed Stage1 ELF extents and unknown inter-object regions.

Metadata-only; original imagefs directory and full source stream are unknown.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

def extent(data,at):
    ehsize,phentsize,phnum,shentsize,shnum,_=struct.unpack_from("<HHHHHH",data,at+40)
    phoff,shoff=struct.unpack_from("<II",data,at+28)
    end=at+max(ehsize,phoff+phentsize*phnum)
    for i in range(phnum):
        p=struct.unpack_from("<IIIIIIII",data,at+phoff+i*phentsize)
        end=max(end,at+p[1]+p[4])
    if shoff and shentsize==40 and 0<shnum<=2048 and at+shoff+shentsize*shnum<=len(data):
        end=max(end,at+shoff+shentsize*shnum)
        for i in range(shnum):
            off=at+shoff+i*40
            typ=struct.unpack_from("<I",data,off+4)[0]
            section_off,section_size=struct.unpack_from("<II",data,off+16)
            if typ!=8:
                end=max(end,at+section_off+section_size)
    return end

def summarize(buf):
    candidates=[e for e in scan_elf(buf) if e["strict_elf_valid"]]
    rows=[]
    for i,e in enumerate(candidates):
        at=e["at"]
        end=extent(buf,at)
        nextat=candidates[i+1]["at"] if i+1<len(candidates) else len(buf)
        capped=min(end,len(buf))
        between=buf[capped:nextat] if capped<=nextat else b""
        nonzero=sum(x!=0 for x in between)
        first_nonzero=next((capped+j for j,x in enumerate(between) if x!=0),None)
        last_nonzero=next((capped+j for j in range(len(between)-1,-1,-1) if between[j]!=0),None)
        rows.append({"elf":hex(at),"type":struct.unpack_from("<H",buf,at+16)[0],
                     "extent_end":hex(end),"minimum_file_bytes":end-at,
                     "next_elf":hex(nextat) if i+1<len(candidates) else None,
                     "between_bytes":max(0,nextat-capped),
                     "between_nonzero":nonzero,
                     "between_first_nonzero":hex(first_nonzero) if first_nonzero is not None else None,
                     "between_last_nonzero":hex(last_nonzero) if last_nonzero is not None else None,
                     "overlaps_next":end>nextat,
                     "extent_inside_decoded":end<=len(buf)})
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        matches=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(matches)!=1:raise ValueError("Ambiguous primary Stage1")
        raw=z.read(matches[0])
    data,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    rows=summarize(data)
    report={"decoded_length":len(data),"strict_elf_count":len(rows),
            "regions":rows,
            "notes":["Extent is a conservative ELF header/segment/section derived end, not proven container file size.",
                     "Nonzero bytes between extents and the next ELF indicate unexplained content; zero-only stretches can be padding.",
                     "Coordinates are relative to an arbitrary unseeded LZF suffix."]}
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
