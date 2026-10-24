#!/usr/bin/env python3
"""Inspect Stage1 entry code with the load-base hypothesis 0x80a00000.

Read-only; optional Capstone is used only for displaying instruction candidates.
"""
import argparse,json,struct,zipfile
from pathlib import Path
BASE=0x80a00000
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Stage1 is missing or ambiguous")
        raw=z.read(members[0])
    data=raw[0xc2:]
    entry=struct.unpack_from("<I",data,0x814)[0]
    header_ptr=struct.unpack_from("<I",data,0x81c)[0]
    off=entry-BASE
    if not 0<=off<len(data):raise ValueError("Entry out of image")
    neighborhoods=[]
    for delta in (-32,-16,0,16,32):
        at=off+delta
        if at<0 or at+32>len(data):continue
        item={"inner_offset":hex(at),"memory_address":hex(BASE+at),
              "bytes_32":data[at:at+32].hex(),
              "words":[hex(struct.unpack_from("<I",data,i)[0]) for i in range(at,at+32,4)]}
        neighborhoods.append(item)
    try:
        from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
        dis=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN)
        instructions=[{"address":hex(i.address),"mnemonic":i.mnemonic,"operands":i.op_str}
                      for i in dis.disasm(data[max(0,off-32):off+96],BASE+max(0,off-32))]
    except ImportError:
        instructions=[]
    result={"hypothesized_image_base":hex(BASE),
            "header_reference":hex(header_ptr),
            "qnx_magic_at_inner":hex(data.find(bytes.fromhex("eb7eff00"))),
            "header_reference_matches":header_ptr==BASE+0x808,
            "branch_target":hex(entry),"entry_inner_offset":hex(off),
            "entry_word":hex(struct.unpack_from("<I",data,off)[0]),
            "entry_aligned_arm":(entry%4==0),
            "neighborhoods":neighborhoods,"arm_disassembly_optional":instructions,
            "caution":"A matching pointer is strong placement evidence but not proof of executed code; Capstone ARM disassembly may decode random data."}
    txt=json.dumps(result,indent=2)+"\n";print(txt,end="")
    if a.json:a.json.write_text(txt)
if __name__=="__main__":main()
