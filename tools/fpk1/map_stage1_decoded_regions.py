#!/usr/bin/env python3
"""Summarize reconstructed Stage1 ELF extents and unknown inter-object regions.

Metadata-only; original imagefs directory and full source stream are unknown.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

def extent(data,at):
    """Return PHDR end and bounded section end; reject impossible SHDRs."""
    ehsize,phentsize,phnum,shentsize,shnum,_=struct.unpack_from("<HHHHHH",data,at+40)
    phoff,shoff=struct.unpack_from("<II",data,at+28)
    ph_end=at+max(ehsize,phoff+phentsize*phnum)
    for i in range(phnum):
        p=struct.unpack_from("<IIIIIIII",data,at+phoff+i*phentsize)
        if p[0] in (1,2,3,4,6,7):
            ph_end=max(ph_end,at+p[1]+p[4])
    section_end=None
    issue=None
    if shoff and shnum:
        if shentsize!=40 or shnum>2048 or at+shoff+40*shnum>len(data):
            issue="invalid_section_table"
        else:
            section_end=at+shoff+40*shnum
            for i in range(shnum):
                off=at+shoff+i*40
                typ=struct.unpack_from("<I",data,off+4)[0]
                fileoff,size=struct.unpack_from("<II",data,off+16)
                if typ!=8:
                    candidate=at+fileoff+size
                    if candidate>len(data):
                        issue="section_extent_out_of_bounds"
                        section_end=None
                        break
                    section_end=max(section_end,candidate)
    return ph_end,section_end,issue

def summarize(buf):
    candidates=[e for e in scan_elf(buf) if e["strict_elf_valid"]]
    rows=[]
    for i,e in enumerate(candidates):
        at=e["at"]
        phend,shend,issue=extent(buf,at)
        nextat=candidates[i+1]["at"] if i+1<len(candidates) else len(buf)
        if shend is not None and shend>nextat:
            issue="section_extent_overlaps_next_elf"
        end=shend if shend is not None and shend<=nextat else phend
        if end>nextat:
            issue="program_extent_overlaps_next_elf"
        between=buf[end:nextat] if end<=nextat else b""
        rows.append({"elf":hex(at),"phdr_extent_end":hex(phend),
                     "section_extent_end":hex(shend) if shend is not None else None,
                     "section_issue":issue,
                     "usable_extent_end":hex(end) if end<=nextat else None,
                     "minimum_file_bytes":end-at if end<=nextat else None,
                     "next_elf":hex(nextat) if i+1<len(candidates) else None,
                     "between_bytes":len(between),
                     "between_nonzero":sum(v!=0 for v in between),
                     "overlaps_next":end>nextat})
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
