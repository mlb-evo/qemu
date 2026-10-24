#!/usr/bin/env python3
"""Assess small pre-padding gaps after accounting for ELF section headers.

Metadata-only: reports boundaries and hashes, not proprietary bytes.
"""
import argparse, hashlib, json, struct, zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf
def inspect(data):
    selected=[e for e in scan_elf(data) if e["strict_elf_valid"]]
    rows=[]
    for i,e in enumerate(selected[:-1]):
        pos=e["at"]; nextpos=selected[i+1]["at"]
        next_zero=nextpos
        while next_zero>0 and data[next_zero-1]==0:next_zero-=1
        phoff=struct.unpack_from("<I",data,pos+28)[0]
        nph=struct.unpack_from("<H",data,pos+44)[0]
        shoff=struct.unpack_from("<I",data,pos+32)[0]
        shentsize,shnum=struct.unpack_from("<HH",data,pos+46)
        phend=max([pos+phoff+32*nph]+[
            pos+fo+fs for j in range(nph)
            for kind,fo,va,pa,fs,ms,fl,al in [struct.unpack_from("<IIIIIIII",data,pos+phoff+32*j)]
            if kind in (1,2,3,4,6,7)])
        shead_end=pos+shoff+shentsize*shnum if shoff and shentsize==40 and shnum<2048 else None
        section_end=None
        if shead_end is not None and shead_end<=len(data):
            ends=[shead_end]
            for j in range(shnum):
                o=pos+shoff+j*shentsize
                typ=struct.unpack_from("<I",data,o+4)[0]
                section_offset,section_size=struct.unpack_from("<II",data,o+16)
                if typ!=8 and pos+section_offset+section_size<=len(data):
                    ends.append(pos+section_offset+section_size)
            section_end=max(ends)
        gap_size=next_zero-phend
        gap=data[phend:next_zero] if 0<=gap_size<=4096 else b""
        rows.append({"elf":hex(pos),"next_elf":hex(nextpos),
                     "phdr_extent_end":hex(phend),
                     "section_extent_end":hex(section_end) if section_end is not None else None,
                     "next_zero_run_start":hex(next_zero),"phdr_to_zero_gap":gap_size,
                     "section_end_minus_phdr_end":section_end-phend if section_end is not None else None,
                     "section_end_within_gap":section_end is not None and phend<=section_end<=next_zero,
                     "gap_sha256_12":hashlib.sha256(gap).hexdigest()[:12] if gap else None,
                     "gap_ascii_ratio":round(sum(32<=x<127 for x in gap)/len(gap),3) if gap else None})
    return rows
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    data,stop,err=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if err:raise ValueError(err)
    rows=inspect(data)
    output=json.dumps({"rows":rows,"note":"Section-table interpretation is provisional; gaps depend on inferred ELF boundaries."},indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
