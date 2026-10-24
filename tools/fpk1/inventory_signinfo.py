#!/usr/bin/env python3
"""Cross-check update SignInfo compression metadata with signed HSP members.

External update compression is distinct from any *internal* IFS encoding.
Read-only. No proprietary binary included.
"""
import argparse
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    results=[]
    with zipfile.ZipFile(a.archive) as z:
        names=set(z.namelist())
        for name in sorted(names):
            if not name.endswith("_SignInfo.xml"):
                continue
            root=ET.fromstring(z.read(name))
            image=name.rsplit("/",1)[0]+"/"+root.attrib["name"]
            if image not in names:
                raise ValueError(f"Missing image for {name}: {image}")
            raw=z.read(image)
            start=int(root.findtext("START-BYTE-FLASHDATA"))
            packed=int(root.findtext("COMPRESSED-SIZE"))
            unpacked=int(root.findtext("UNCOMPRESSED-SIZE"))
            if start < 0 or start+packed > len(raw):
                raise ValueError(f"Invalid bounds: {image}")
            results.append({
                "image":image,"block_id":root.findtext("BLOCK-ID"),
                "hsp_flashdata_offset":start,
                "stored_bytes":packed,
                "uncompressed_bytes_in_signinfo":unpacked,
                "externally_compressed":packed!=unpacked,
                "stored_size_matches_remaining_bytes":len(raw)-start==packed,
                "signed_member_length":len(raw),
            })
    output=json.dumps(results,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
