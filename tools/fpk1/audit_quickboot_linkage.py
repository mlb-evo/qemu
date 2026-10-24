#!/usr/bin/env python3
"""Audit FPK1 Quickboot external ARM BL references and DRAM literals.

Read-only: scans only supplied archive entries, never patches firmware.
All branch targets are FILE-RELATIVE, not runtime addresses.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

LITERALS = (0x8401891c, 0x84068088, 0x84068083)
def branch_target(word, at):
    if (word & 0x0f000000) != 0x0b000000:
        return None
    imm = word & 0xffffff
    if imm & 0x800000:
        imm -= 1 << 24
    return at + 8 + imm * 4

def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/qb_primary.img")]
        if len(names)!=1: raise ValueError("Missing unique qb_primary.img")
        code=z.read(names[0])[0xc2:]
        calls=[]
        for at in range(0, min(0x78,len(code)),4):
            word=struct.unpack_from("<I",code,at)[0]
            target=branch_target(word,at)
            if target is not None:
                calls.append(dict(at=hex(at),instruction=f"{word:08x}",target_file_relative=target,
                                  target_in_quickboot=0 <= target < len(code)))
        hits={}
        for path in z.namelist():
            if not path.endswith((".img",".bin")):continue
            data=z.read(path)
            occurrences={f"0x{v:08x}":data.count(struct.pack("<I",v)) for v in LITERALS}
            if any(occurrences.values()):hits[path]=occurrences
    report={"quickboot_size":len(code),"quickboot_sha256":hashlib.sha256(code).hexdigest(),
            "arm_bl_calls_in_first_0x78":calls,
            "literal_occurrences_in_update_components":hits,
            "caveat":"No load base, relocation table or standalone boot entry established."}
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if args.json:args.json.write_text(output)

if __name__=="__main__":main()
