#!/usr/bin/env python3
"""Inspect the three Stage1 ELF objects missing adjacent QNX NAME metadata.

Diagnostic only; printable strings are clues, not verified filenames.
"""
import argparse,json,re,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf
from identify_stage1_elf_dependencies import inspect_elf

TARGETS=(0xbbb8e,0xfb4a0,0x11f7a8)
KEYWORDS=re.compile(rb"[\x20-\x7e]{6,160}")

def inspect(data,at,nextat):
    header=inspect_elf(data,at)
    raw=data[at:nextat]
    hits=[]
    terms=(b"NAME=",b"DESCRIPTION=",b"QNX",b"nvidia",b"nv",b"mount",
           b"clock",b"boot",b"driver",b"usage",b"Usage",b"error",b"Error")
    for m in KEYWORDS.finditer(raw):
        string=m.group()
        if any(term.lower() in string.lower() for term in terms):
            hits.append({"at":hex(at+m.start()),"text":string[:120].decode("ascii")})
            if len(hits)>=30:break
    return {"offset":hex(at),"until_next_elf":hex(nextat),
            "elf":header,"selected_strings":hits,
            "caution":"String selection is heuristic and may include adjoining content."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    data,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    all_elf=sorted(e["at"] for e in scan_elf(data) if e["strict_elf_valid"])
    rows=[]
    for at in TARGETS:
        if at not in all_elf:raise ValueError("Unknown ELF no longer strict-valid: "+hex(at))
        idx=all_elf.index(at)
        rows.append(inspect(data,at,all_elf[idx+1] if idx+1<len(all_elf) else len(data)))
    result=json.dumps({"strict_elf_total":len(all_elf),"unidentified":rows},indent=2)+"\n"
    print(result,end="")
    if a.json:a.json.write_text(result)
if __name__=="__main__":main()
