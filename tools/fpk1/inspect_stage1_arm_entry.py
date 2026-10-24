#!/usr/bin/env python3
"""Analyze the Stage1 ARM PC-relative jump and QNX startup address relationships.

Read-only. Distinguishes literal target, image base hypotheses and raw
header words; does not infer a working QEMU boot address.
"""
import argparse,json,struct,zipfile
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(members[0])
    d=raw[0xc2:]
    first,second=struct.unpack_from("<II",d,0x800)
    if (first,second)!=(0xe28fc00c,0xe59cf000):
        raise ValueError("Unknown ARM boot stub")
    # ARM state PC reads address of current instruction +8.
    # add ip,pc,#12 at 0x800 -> ip=0x814, ldr pc,[ip] -> literal at +0x814.
    literal_offset=0x800+8+12
    target=struct.unpack_from("<I",d,literal_offset)[0]
    startup_vaddr=struct.unpack_from("<I",d,0x81c)[0]
    offset_delta=target-startup_vaddr
    candidates=[]
    for base in (0x80a00000,0x80a00800,0x80a00808,0x80000000):
        entry=target-base
        candidates.append({"hypothetical_load_base":hex(base),
                           "target_minus_base":hex(entry),
                           "entry_inside_inner":0<=entry<len(d),
                           "entry_first_16":d[entry:entry+16].hex() if 0<=entry<len(d) else None})
    result={
      "image_size":hex(len(d)),
      "stub_at":"0x800",
      "literal_offset":hex(literal_offset),
      "branch_target":hex(target),
      "word_at_0x81c":hex(startup_vaddr),
      "difference_target_minus_word_0x81c":hex(offset_delta),
      "words_0x800_0x840":[{"offset":hex(i),"le_word":hex(struct.unpack_from("<I",d,i)[0])} for i in range(0x800,0x840,4)],
      "load_base_hypotheses":candidates,
      "note":"Target computed from ARM instruction semantics; base and execution mode are hypotheses."
    }
    out=json.dumps(result,indent=2)+"\n";print(out,end="")
    if a.json:a.json.write_text(out)
if __name__=="__main__":main()
