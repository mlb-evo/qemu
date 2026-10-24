#!/usr/bin/env python3
"""Locate early-boot mount and launch strings in FPK1 Stage1/Stage2 payloads.

Read-only forensic *string references*, not script extraction. Byte offsets are
relative to the historical candidate-inner payload raw[0xc2:]; additionally
reports exact archive-member and SignInfo FLASHDATA coordinates.
"""
import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

IMAGES=("stage1_ifs.img","stage1_RECOVERY_ifs.img","stage2_ifs.img")
PATTERNS=(
    rb"/stage3",rb"/mnt/stage3",rb"stage3\.sh",
    rb"startup\.sh",rb"startup-common\.sh",
    rb"mount",rb"fs-qnx6",rb"devb-mmcsd",
    rb"devf-tegra",rb"procnto",rb"startup-nvidia",
    rb"/mnt/persist_fpk",rb"/mnt/temp_fpk",
)
MIN_LEN=4
MAX_LINE=384
MAX_MATCHES=40

def ascii_lines(buf):
    # Strings of printable ASCII; no inference that strings are executed.
    for m in re.finditer(rb"[\x20-\x7e]{4,}",buf):
        yield m.start(),m.group()

def analyze(z,member,offset,stored):
    raw=z.read(member)
    if len(raw)<offset+stored:raise ValueError("Truncated FLASHDATA: "+member)
    # Signed flashdata includes its own eight-byte marker; candidate inner
    # starts eight bytes later. Exclude the external HSP tail.
    flash=raw[offset:offset+stored]
    inner=flash[8:]
    result={"member":member,"flashdata_offset":offset,
            "flashdata_stored_size":stored,
            "flashdata_prefix":flash[:8].hex(),
            "candidate_inner_size":len(inner),
            "hits":[]}
    counts={p.decode():0 for p in PATTERNS}
    for start,s in ascii_lines(inner):
        low=s.lower()
        matching=[p for p in PATTERNS if re.search(p,low)]
        if not matching:continue
        for p in matching:counts[p.decode()]+=1
        if len(result["hits"])>=MAX_MATCHES:continue
        if len(s)>MAX_LINE:s=s[:MAX_LINE]
        result["hits"].append({
            "inner_offset":hex(start),
            "flashdata_relative_offset":hex(start+8),
            "member_raw_offset":hex(start+offset+8),
            "text":s.decode("ascii","replace"),
            "matched":[p.decode() for p in matching],
        })
    result["counts"]=counts
    result["truncated_hits"]=sum(counts.values())>MAX_MATCHES
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--json",type=Path)
    opts=parser.parse_args()
    results={}
    with zipfile.ZipFile(opts.archive) as z:
        for xmlname in z.namelist():
            if not xmlname.endswith("_SignInfo.xml"):continue
            meta=ET.fromstring(z.read(xmlname))
            base=meta.attrib.get("name")
            if base not in IMAGES:continue
            member=xmlname.rsplit("/",1)[0]+"/"+base
            results[base]=analyze(
                z,member,int(meta.findtext("START-BYTE-FLASHDATA")),
                int(meta.findtext("COMPRESSED-SIZE")))
    if set(results)!=set(IMAGES):raise ValueError("Missing Stage1 or Stage2 member")
    out=json.dumps(results,indent=2)+"\n"
    print(out,end="")
    if opts.json:opts.json.write_text(out)

if __name__=="__main__":
    main()
