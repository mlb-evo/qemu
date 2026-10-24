#!/usr/bin/env python3
"""Inspect ARM Stage1 startup region and possible compressed-data boundaries.

Read-only; disassembles a few ARM words as words, not full control flow.
Reports early code literals and QNX signatures in inner coordinates.
"""
import argparse,json,struct,zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    p.add_argument("--window",type=lambda s:int(s,0),default=0x1000)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Stage1 primary not unique")
        raw=z.read(names[0])
    data=raw[0xc2:]
    if data[0x800:0x804]!=bytes.fromhex("0cc08fe2"):
        raise ValueError("Unexpected Stage1 ARM prefix")
    vals=[]
    for off in range(0x800,min(len(data),0x800+a.window),4):
        v=struct.unpack_from("<I",data,off)[0]
        if v:
            vals.append({"offset":hex(off),"arm_word":hex(v),
                "as_inner_pointer":v<len(data),
                "as_tegra_address":0x80000000<=v<=0xffffffff})
    needles={"qnx_magic":bytes.fromhex("eb7eff00"),
             "startup_label":b"startup-nvidia-tegra3-mm",
             "imagefs":b"imagefs",
             "fs_qnx6":b"fs-qnx6"}
    matches={}
    for name,needle in needles.items():
        found=[];idx=0
        while (idx:=data.find(needle,idx))!=-1:
            found.append(hex(idx));idx+=len(needle)
            if len(found)>=20:break
        matches[name]=found
    result={"stage1_inner_size":hex(len(data)),"arm_first_16":data[0x800:0x810].hex(),
            "arm_prefix_meaning":"ARM little-endian instruction bytes; no automatic branch decoding",
            "first_code_words":vals[:120],"signatures":matches,
            "caution":"Raw memory-looking words are not established load addresses or LZF framing."}
    payload=json.dumps(result,indent=2)+"\n"
    print(payload,end="")
    if a.json:a.json.write_text(payload)
if __name__=="__main__":main()
