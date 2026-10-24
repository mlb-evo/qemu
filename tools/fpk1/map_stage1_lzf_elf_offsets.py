#!/usr/bin/env python3
"""Map decoded ELF starts back to LZF token positions in encoded Stage1.

Metadata only, no firmware binaries exported. Mappings refer to the
chosen suffix's decoded coordinate system; stream framing is unverified.
"""
import argparse
import bisect
import json
import struct
import zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode, scan_elf

START=0x1318fc
END=0x1f6ffb

def token_boundaries(data,start,end):
    position=start
    decoded=0
    tokens=[]
    while position<end:
        token_start=position
        ctrl=data[position]
        position+=1
        if ctrl<32:
            length=ctrl+1
            if position+length>end:raise ValueError("literal past boundary")
            position+=length
            kind="literal"
        else:
            length=ctrl>>5
            if length==7:
                if position>=end:raise ValueError("missing length")
                length+=data[position]
                position+=1
            if position>=end:raise ValueError("missing distance")
            distance=((ctrl&31)<<8)+data[position]+1
            position+=1
            length+=2
            if distance>decoded:raise ValueError("invalid history")
            kind="reference"
        tokens.append((decoded,decoded+length,token_start,position,kind))
        decoded+=length
    return tokens,decoded

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    inner=raw[0xc2:]
    decoded,stop,error=decode(inner[:END],START)
    if stop!=END or error is not None:raise ValueError("Expected clean bounded suffix")
    tokens,size=token_boundaries(inner,START,END)
    if size!=len(decoded):raise ValueError("Token trace disagrees with decoder")
    starts=[t[0] for t in tokens]
    entries=[]
    elfs=[e for e in scan_elf(decoded) if e["strict_elf_valid"]]
    for e in elfs:
        offset=e["at"]
        index=bisect.bisect_right(starts,offset)-1
        a,b,enc_start,enc_end,kind=tokens[index]
        entries.append({
            "decoded_elf":hex(offset),
            "encoded_token_start":hex(enc_start),
            "encoded_token_end":hex(enc_end),
            "token_kind":kind,
            "within_decoded_token":offset-a,
            "decoded_token_length":b-a,
            "encoded_distance_from_previous_elf":None if not entries else enc_start-int(entries[-1]["encoded_token_start"],16),
            "decoded_distance_from_previous_elf":None if not entries else offset-int(entries[-1]["decoded_elf"],16),
            "preceding_encoded_16":inner[max(START,enc_start-16):enc_start].hex(),
        })
    report={"chosen_suffix_start":hex(START),"chosen_suffix_end":hex(END),
            "decoded_length":len(decoded),"lzf_token_count":len(tokens),
            "strict_elf_count":len(entries),"elf_positions":entries,
            "warning":"Encoded offsets identify token positions, not original ELF file or LZF chunk boundaries."}
    text=json.dumps(report,indent=2)+"\n"
    print(text,end="")
    if args.json:args.json.write_text(text)
if __name__=="__main__":main()
