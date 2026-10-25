#!/usr/bin/env python3
"""Read-only SIFS loader evidence: strings and ELF section ranges.

Offsets refer to decoded LZF suffix, NOT an authenticated SIFS file format.
Only prints diagnostic strings and numeric metadata; never extracts binaries.
"""
import argparse,json,re,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf
from identify_stage1_elf_dependencies import inspect_elf

ELF_AT=0xfb4a0
FIND=re.compile(rb"[\x20-\x7e]{5,240}")
NEEDLES=("sifs","image","mount","partition","block","checksum","compress",
         "decompress","version","nand","nordma","usage","header","error")

def inspect(data):
    candidates=sorted(e["at"] for e in scan_elf(data) if e["strict_elf_valid"])
    if ELF_AT not in candidates:raise ValueError("sifsloader ELF not strict-valid")
    next_at=candidates[candidates.index(ELF_AT)+1]
    header=inspect_elf(data,ELF_AT)
    phoff=struct.unpack_from("<I",data,ELF_AT+28)[0]
    phnum=struct.unpack_from("<H",data,ELF_AT+44)[0]
    segments=[]
    for i in range(phnum):
        typ,off,va,pa,fs,ms,flags,align=struct.unpack_from(
            "<IIIIIIII",data,ELF_AT+phoff+32*i)
        segments.append({"type":hex(typ),"offset":hex(off),"vaddr":hex(va),
                         "filesz":fs,"memsz":ms,"align":hex(align)})
    strings=[]
    for m in FIND.finditer(data,ELF_AT,next_at):
        val=m.group().decode("ascii")
        if any(n in val.lower() for n in NEEDLES):
            strings.append({"decoded_at":hex(m.start()),"relative_to_elf":hex(m.start()-ELF_AT),
                            "text":val[:200]})
    return {"elf_at":hex(ELF_AT),"next_elf":hex(next_at),
            "elf":header,"segments":segments,
            "strings":strings[:150],"string_matches":len(strings),
            "limitations":["String references do not prove the on-disk SIFS structure.",
                           "Cannot infer checksums/compression algorithms without tracing implementation.",
                           "Next ELF boundary does not prove this ELF's true file size."]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path);parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    if raw[:3]!=b"HSP":raise ValueError("Not HSP Stage1")
    buf,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error or stop!=0x1f6ffb:raise ValueError("Unexpected decode boundary")
    report={"source_encoded_stop":hex(stop),**inspect(buf)}
    output=json.dumps(report,indent=2)+"\n";print(output,end="")
    if args.json:args.json.write_text(output)

if __name__=="__main__":main()
