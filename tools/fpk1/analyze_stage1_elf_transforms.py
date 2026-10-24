#!/usr/bin/env python3
"""Compare apparent Stage1 ELF magic contexts to a normal ELF32 ARM header.

The offsets are raw candidate-inner Stage1 (HSP member +0xc2). This probe
does not decode, extract, or alter firmware. ELF magic alone is insufficient.
"""
import argparse,json,struct,zipfile
from collections import Counter
from pathlib import Path

MAGIC=b"\x7fELF"
TEMPLATE=b"\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        matches=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(matches)!=1:raise ValueError("Stage1 primary member missing/ambiguous")
        data=z.read(matches[0])[0xc2:]
    rows=[]
    pos=0
    while (pos:=data.find(MAGIC,pos))>=0:
        if pos+64<=len(data):
            h=data[pos:pos+64]
            machine=struct.unpack_from("<H",h,18)[0]
            rows.append({"offset":hex(pos),"header_64":h.hex(),
                         "ident_16":h[:16].hex(),
                         "ident_first_7_matches_elf32_le":h[:7]==TEMPLATE[:7],
                         "e_machine_raw":hex(machine),
                         "raw_header_ehsize":struct.unpack_from("<H",h,40)[0],
                         "raw_e_version":hex(struct.unpack_from("<I",h,20)[0]),
                         "preceding_8":data[max(0,pos-8):pos].hex(),
                         "has_4byte_preceding_marker":pos>=4 and data[pos-4]==0xe0 and data[pos-2:pos]==b"\x00\x05" or pos>=4 and data[pos-4]==0xe0 and data[pos-2:pos]==b"\x00\x06"})
        pos+=4
    hist=Counter(r["ident_16"] for r in rows)
    result={"coordinate_system":"Stage1 raw HSP member +0xc2",
            "total_elf_magic":len(rows),
            "elf_magic_after_four_byte_marker":sum(r["has_4byte_preceding_marker"] for r in rows),
            "most_common_ident16":hist.most_common(12),
            "headers":rows}
    out=json.dumps(result,indent=2)+"\n"
    print(out,end="")
    if args.json:args.json.write_text(out)
if __name__=="__main__":main()
