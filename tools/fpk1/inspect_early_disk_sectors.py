#!/usr/bin/env python3
"""Inspect early sectors and differences of zlib-expanded FPK1 disk images.

Uses XML-declared FLASHDATA offsets, validates the zlib stream, and reports
only hashes/hex samples. Does not write extracted firmware.
"""
import argparse, hashlib, json, xml.etree.ElementTree as ET, zipfile, zlib
from pathlib import Path

SECTOR=512
TARGETS=("app.img","stage3.img")

def load(z,target):
    for entry in z.namelist():
        if not entry.endswith("_SignInfo.xml"):continue
        root=ET.fromstring(z.read(entry))
        if root.attrib.get("name")!=target:continue
        member=entry.rsplit("/",1)[0]+"/"+target
        raw=z.read(member)
        begin=int(root.findtext("START-BYTE-FLASHDATA"))
        size=int(root.findtext("COMPRESSED-SIZE"))
        expected=int(root.findtext("UNCOMPRESSED-SIZE"))
        if expected>256*1024*1024 or expected%SECTOR:raise ValueError("Bad expected size")
        dec=zlib.decompressobj()
        output=dec.decompress(raw[begin:begin+size],expected+1)
        output+=dec.flush()
        if not dec.eof or dec.unused_data or len(output)!=expected:raise ValueError("Invalid zlib image")
        return output
    raise ValueError("Missing "+target)

def section(data,lba):
    b=data[lba*SECTOR:(lba+1)*SECTOR]
    return {"lba":lba,"offset":hex(lba*SECTOR),
            "sha256":hashlib.sha256(b).hexdigest(),
            "nonzero_count":sum(x!=0 for x in b),
            "first_64":b[:64].hex(),
            "last_32":b[-32:].hex(),
            "ascii_first_64":"".join(chr(x) if 32<=x<127 else "." for x in b[:64])}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        images={k:load(z,k) for k in TARGETS}
    a,b=(images[k] for k in TARGETS)
    if len(a)!=len(b):raise ValueError("Unequal image length")
    lbas=(0,1,2,3,4,7,8,9,15,16,17,18,19,20,24,25,26,27,28,32,33,40,63,64,83,84,85,127,128,255,256,511,512)
    results={"first_difference_byte":next((i for i in range(len(a)) if a[i]!=b[i]),None),
             "sampled_sectors":{},
             "early_sector_differences":[]}
    for k,d in images.items():
        results["sampled_sectors"][k]=[section(d,lba) for lba in lbas]
    for lba in range(256):
        start=lba*SECTOR
        if a[start:start+SECTOR]!=b[start:start+SECTOR]:
            results["early_sector_differences"].append(lba)
    rendered=json.dumps(results,indent=2)+"\n"
    print(rendered,end="")
    if args.json:args.json.write_text(rendered)

if __name__=="__main__":main()
