#!/usr/bin/env python3
"""Test candidate LZF logical end versus raw Stage1 HSP header fields.

Read-only. Reports bounded decoding and 5-byte suffix, does not assume the
candidate is the authentic chunk terminator.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

END=0x1f6ffb
STARTS=(0x1318fc,0x18d9fe,0x194216,0x1c14f5)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Ambiguous primary Stage1")
        raw=z.read(members[0])
    if raw[:3]!=b"HSP":raise ValueError("HSP missing")
    inner=raw[0xc2:]
    if len(inner)<END:raise ValueError("Unexpected short inner Stage1")
    rows=[]
    for start in STARTS:
        # Slice end at the last complete token boundary from earlier tracing.
        out,stop,error=decode(inner[:END],start)
        es=scan_elf(out)
        rows.append({"start":hex(start),"decoded":len(out),"stop":hex(stop),
                     "error":error,"strict_elf":sum(e["strict_elf_valid"] for e in es),
                     "elf_candidates":len(es)})
    # Header word probes are values only, no inferred semantics.
    head=[{"offset":hex(i),"u32_le":hex(struct.unpack_from("<I",inner,i)[0]),
           "u32_be":hex(struct.unpack_from(">I",inner,i)[0])}
          for i in range(0,64,4)]
    report={"inner_length":hex(len(inner)),"candidate_lzf_end":hex(END),
            "tail_hex":inner[END:].hex(),"tail_length":len(inner)-END,
            "original_member_size":len(raw),"hsp_first_32":raw[:32].hex(),
            "inner_first_32":inner[:32].hex(),"inner_header_words":head,
            "results":rows,
            "caution":"A clean suffix decode at a chosen endpoint is not proof that its header describes LZF or that it is an original block boundary."}
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
