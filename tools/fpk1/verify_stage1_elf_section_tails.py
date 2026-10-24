#!/usr/bin/env python3
"""Check whether Stage1 ELF section tails account for the apparent small gaps.

Read-only, reports offsets, sizes and zero-fill. No firmware bytes exported.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

def analyze(data):
    elfs=[e for e in scan_elf(data) if e["strict_elf_valid"]]
    rows=[]
    for idx,e in enumerate(elfs[:-1]):
        base=e["at"]; nxt=elfs[idx+1]["at"]
        shoff=struct.unpack_from("<I",data,base+32)[0]
        entsize,count=struct.unpack_from("<HH",data,base+46)
        if not shoff or entsize!=40 or count>2048 or base+shoff+entsize*count>len(data):
            continue
        sections=[]
        end=base+shoff+entsize*count
        for i in range(count):
            off=base+shoff+entsize*i
            name,stype,flags,addr,fileoff,size,link,info,align,ents=struct.unpack_from("<IIIIIIIIII",data,off)
            if stype!=8:
                candidate=base+fileoff+size
                if candidate<=len(data):end=max(end,candidate)
            sections.append({"index":i,"type":stype,"offset":fileoff,"size":size})
        runstart=nxt
        while runstart>0 and data[runstart-1]==0:runstart-=1
        rows.append({"elf":hex(base),"next_elf":hex(nxt),
                     "section_end":hex(end),"zero_run_start":hex(runstart),
                     "difference_section_end_minus_zero_start":end-runstart,
                     "padding_after_section_end":nxt-end,
                     "trailing_byte_before_section_end":hex(data[end-1]) if end else None,
                     "first_byte_after_section_end":hex(data[end]) if end<len(data) else None,
                     "section_header_count":count,
                     "last_sections":sections[-4:]})
    return rows

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        m=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(m)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(m[0])
    decoded,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    rows=analyze(decoded)
    output=json.dumps({"rows":rows,"note":"Section extents are derived from ELF section headers; full file/container boundaries remain unproven."},indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
