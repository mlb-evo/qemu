#!/usr/bin/env python3
"""Correlate QNX NAME/DESCRIPTION build metadata with decoded Stage1 ELF.

Read-only: metadata only, not a verified imagefs catalog or file extraction.
"""
import argparse,json,re,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

PAT=re.compile(rb"(?:NAME|DESCRIPTION|DATE|STATE|HOST|USER)=[\x20-\x7e]{1,200}")
def analyze(data):
    elfs=[e for e in scan_elf(data) if e["strict_elf_valid"]]
    metadata=[]
    for match in PAT.finditer(data):
        raw=match.group().decode("ascii","replace")
        key,val=raw.split("=",1)
        # Stop at format boundaries where possible.
        val=val.split("\x00")[0]
        prev=max((e["at"] for e in elfs if e["at"]<=match.start()),default=None)
        nxt=min((e["at"] for e in elfs if e["at"]>match.start()),default=None)
        metadata.append({"at":hex(match.start()),"key":key,"value":val,
                         "previous_elf":hex(prev) if prev is not None else None,
                         "offset_from_previous_elf":match.start()-prev if prev is not None else None,
                         "next_elf":hex(nxt) if nxt is not None else None})
    groups=[]
    for e in elfs:
        at=e["at"]
        entries=[x for x in metadata if x["previous_elf"]==hex(at)]
        groups.append({"elf":hex(at),"type":struct.unpack_from("<H",data,at+16)[0],
                       "metadata":entries[:40],
                       "candidate_name":next((x["value"] for x in entries if x["key"]=="NAME"),None)})
    return {"elfs":groups,"all_metadata_count":len(metadata),
            "unassigned_metadata":[m for m in metadata if m["previous_elf"] is None]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    args=p.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(members[0])
    decoded,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    result={"decoded_length":len(decoded),"source_stop":hex(stop),**analyze(decoded),
            "warning":"Nearest preceding ELF is a heuristic grouping, not proven metadata ownership."}
    text=json.dumps(result,indent=2)+"\n"
    print(text,end="")
    if args.json:args.json.write_text(text)
if __name__=="__main__":main()
