#!/usr/bin/env python3
"""Correlate recovered Stage1 ELF extents with nearby QNX path-like strings.

No proprietary binary extraction; candidate names are NOT proven imagefs names.
"""
import argparse
import json
import re
import struct
import zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode, scan_elf

END = 0x1f6ffb
PATH = re.compile(rb"(?:[A-Za-z0-9_.+-]+/){1,6}[A-Za-z0-9_.+-]+|(?:lib[A-Za-z0-9_.+-]+\.so(?:\.[0-9]+)*)")
def strings(window, base, limit=15):
    matches = []
    for match in PATH.finditer(window):
        if len(matches) >= limit:
            break
        matches.append({"at":hex(base + match.start()),
                        "text":match.group().decode("ascii"),
                        "relative_offset":match.start()})
    return matches

def inventory(data, window):
    elfs=[e for e in scan_elf(data) if e["strict_elf_valid"]]
    items=[]
    for e in elfs:
        at=e["at"]
        phoff=struct.unpack_from("<I",data,at+28)[0]
        phnum=struct.unpack_from("<H",data,at+44)[0]
        file_end=0
        for i in range(phnum):
            ph=struct.unpack_from("<IIIIIIII",data,at+phoff+32*i)
            if ph[0] in (1,2,3,4,6,7):
                file_end=max(file_end,ph[1]+ph[4])
        before=max(0,at-window)
        after=min(len(data),at+file_end+window)
        candidate_end=min(len(data),at+file_end)
        items.append({
            "elf_at":hex(at),
            "file_extent_end_candidate":hex(candidate_end),
            "extent_within_buffer":at+file_end<=len(data),
            "nearest_preceding_elf":hex(elfs[elfs.index(e)-1]["at"]) if elfs.index(e)>0 else None,
            "next_elf":hex(elfs[elfs.index(e)+1]["at"]) if elfs.index(e)+1<len(elfs) else None,
            "pathlike_before":strings(data[before:at],before),
            "pathlike_after_extent":strings(data[candidate_end:after],candidate_end),
            "gap_to_next_elf":(elfs[elfs.index(e)+1]["at"]-candidate_end)
               if elfs.index(e)+1<len(elfs) else None
        })
    return items

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--json",type=Path)
    parser.add_argument("--window",type=int,default=512)
    args=parser.parse_args()
    if args.window<16 or args.window>4096:
        parser.error("--window must be 16..4096")
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:
            raise ValueError("Ambiguous Stage1 primary image")
        raw=z.read(names[0])
    if raw[:3]!=b"HSP":
        raise ValueError("Expected HSP wrapper")
    decoded,stop,error=decode(raw[0xc2:0xc2+END],0x1318fc)
    data={"source_start":"0x1318fc","source_end":hex(stop),
          "decode_error":error,"items":inventory(decoded,args.window),
          "warning":"String proximity is NOT QNX imagefs catalog evidence; ELF extents are inferred from PHDR only."}
    result=json.dumps(data,indent=2)+"\n"
    print(result,end="")
    if args.json:
        args.json.write_text(result)
if __name__=="__main__":
    main()
