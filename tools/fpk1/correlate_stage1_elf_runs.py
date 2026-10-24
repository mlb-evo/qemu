#!/usr/bin/env python3
"""Correlate Stage1 E0FF00 padding-like runs with apparent ELF headers.

Read-only; reports bytes/offsets only, never writes firmware payloads.
ELF headers are *candidates*: magic alone does not imply a valid ELF file.
All offsets relative to unwrapped image at HSP member +0xc2.
"""
import argparse,json,struct,zipfile
from collections import Counter
from pathlib import Path
PAT=b"\xe0\xff\x00"
ELF=b"\x7fELF"
def scan(data):
    runs=[]
    p=0
    while (p:=data.find(PAT,p))!=-1:
        start=p
        while data[p:p+3]==PAT:p+=3
        count=(p-start)//3
        if count<4:
            p=start+1
            continue
        hits=[]
        search_start=p
        for _ in range(3):
            at=data.find(ELF,search_start,min(len(data),p+128))
            if at<0:break
            ident=data[at:at+16]
            candidate={"offset":hex(at),"distance_after_run":at-p,
                       "ident_hex":ident.hex(),"ei_class":ident[4] if len(ident)>4 else None,
                       "ei_data":ident[5] if len(ident)>5 else None,
                       "ei_version":ident[6] if len(ident)>6 else None}
            if len(data)>=at+52:
                candidate.update({"e_type":struct.unpack_from("<H",data,at+16)[0],
                                  "e_machine":struct.unpack_from("<H",data,at+18)[0],
                                  "e_version":struct.unpack_from("<I",data,at+20)[0],
                                  "e_phoff":struct.unpack_from("<I",data,at+28)[0],
                                  "e_ehsize":struct.unpack_from("<H",data,at+40)[0],
                                  "e_phentsize":struct.unpack_from("<H",data,at+42)[0]})
                candidate["plausible_elf32_arm_header"]=(
                    ident[4:7]==b"\x01\x01\x01" and candidate["e_machine"]==40
                    and candidate["e_version"]==1 and candidate["e_ehsize"]==52
                    and candidate["e_phentsize"] in (0,32))
            hits.append(candidate)
            search_start=at+1
        runs.append({"start":hex(start),"end":hex(p),"triples":count,
                     "bytes":3*count,"following_16":data[p:p+16].hex(),
                     "elf_hits_within_128":hits})
    distances=Counter(h["distance_after_run"] for r in runs for h in r["elf_hits_within_128"])
    return {"total_runs":len(runs),
            "runs_with_nearby_elf":sum(bool(r["elf_hits_within_128"]) for r in runs),
            "distances_after_run":dict(sorted(distances.items())),
            "runs":runs}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Expected exactly one Stage1")
        raw=z.read(names[0])
        if raw[:3]!=b"HSP":raise ValueError("HSP signature not found")
    result=scan(raw[0xc2:])
    output=json.dumps(result,indent=2)+"\n"
    print(output,end="")
    if args.json:args.json.write_text(output)
if __name__=="__main__":main()
