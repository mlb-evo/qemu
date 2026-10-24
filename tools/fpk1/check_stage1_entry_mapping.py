#!/usr/bin/env python3
"""Compare Stage1 branch target as raw versus post-decompression address.

Read-only: scans plausible ARM instruction density around raw target and
checks whether a decoded LZF suffix spans that logical image offset.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode
BASE=0x80a00000
def arm_conditions(data,start,n=64):
    words=[struct.unpack_from("<I",data,start+i*4)[0] for i in range(n)]
    return {"words":len(words),
            "cond_always":sum((w>>28)==14 for w in words),
            "cond_never":sum((w>>28)==15 for w in words),
            "branch_pattern":sum((w&0x0e000000)==0x0a000000 for w in words)}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive");p.add_argument("--json")
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(members[0])
    src=raw[0xc2:]
    entry=struct.unpack_from("<I",src,0x814)[0]
    off=entry-BASE
    if not 0<=off<len(src)-256:raise ValueError("Entry offset out of bounds")
    result={"raw_entry_offset":hex(off),"entry_target":hex(entry),
            "raw_entry_arm_heuristic":arm_conditions(src,off),
            "early_stub_arm_heuristic":arm_conditions(src,0x800),
            "decoded_suffix_check":[]}
    for start in (0x1318fc,0x18d9fe):
        decoded,stop,error=decode(src[:0x1f6ffb],start)
        result["decoded_suffix_check"].append({
            "compressed_start":hex(start),"decoded_length":len(decoded),
            "enough_decoded_bytes_to_contain_entry_offset":len(decoded)>off+256,
            "decoded_at_same_offset_arm_heuristic":arm_conditions(decoded,off)
                if len(decoded)>=off+256 else None,
            "caution":"Decoded suffix logical index is NOT proven to equal original image offset."
        })
    output=json.dumps(result,indent=2)+"\n";print(output,end="")
    if a.json:__import__("pathlib").Path(a.json).write_text(output)
if __name__=="__main__":main()
