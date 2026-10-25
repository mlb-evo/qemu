#!/usr/bin/env python3
"""Map all Stage1 QNX NAME records to nearby ELF headers and candidate boundaries.

Read-only forensic coordinates, not a reconstructed filesystem catalog.
"""
import argparse,bisect,json,struct,zipfile
from pathlib import Path
from cluster_stage1_qnx_build_records import collect
from validate_stage1_unseeded_lzf import decode,scan_elf

START=0x1318fc
END=0x1f6ffb

def examine(buf):
    elfs=sorted(e["at"] for e in scan_elf(buf) if e["strict_elf_valid"])
    starts=[int(x["start"],16) for x in collect(buf)]
    records=collect(buf)
    result=[]
    for i,rec in enumerate(records):
        at=starts[i]
        idx=bisect.bisect_right(elfs,at)-1
        prev=elfs[idx] if idx>=0 else None
        following=elfs[idx+1] if idx+1<len(elfs) else None
        local_start=max(0,at-128)
        neighborhood=buf[local_start:at]
        # Do not dump firmware bytes; report meaningful layout markers only.
        nearest_elf_magic=buf.rfind(b"\x7fELF",max(0,at-262144),at)
        if nearest_elf_magic<0:nearest_elf_magic=None
        result.append({
            "record_start":hex(at),
            "name":rec["fields"]["NAME"],
            "description":rec["fields"].get("DESCRIPTION"),
            "record_fields":rec["fields"],
            "preceding_strict_elf":hex(prev) if prev is not None else None,
            "offset_from_preceding_elf":at-prev if prev is not None else None,
            "next_strict_elf":hex(following) if following is not None else None,
            "distance_to_next_strict_elf":following-at if following is not None else None,
            "nearest_preceding_elf_magic":hex(nearest_elf_magic) if nearest_elf_magic is not None else None,
            "nearest_magic_is_strict":nearest_elf_magic in elfs if nearest_elf_magic is not None else False,
            "zero_bytes_in_previous_128":neighborhood.count(0),
            "distance_to_previous_NAME":at-starts[i-1] if i else None
        })
    collisions=[{"elf":hex(elf),"names":[r["name"] for r in result if r["preceding_strict_elf"]==hex(elf)]}
                for elf in elfs]
    return {"strict_elf_count":len(elfs),"name_count":len(records),
            "name_records":result,"elf_windows":collisions,
            "warning":"Proximity to ELF does not prove ownership; NAME records can be embedded in ELF tails or in other objects."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    if raw[:3]!=b"HSP":raise ValueError("Expected HSP")
    decoded,stop,error=decode(raw[0xc2:0xc2+END],START)
    if error or stop!=END:raise ValueError("Unexpected suffix decode boundary")
    report={"encoded_start":hex(START),"encoded_end":hex(stop),
            "decoded_bytes":len(decoded),**examine(decoded)}
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)

if __name__=="__main__":main()
