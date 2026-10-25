#!/usr/bin/env python3
"""Explain why secondary ARM ELF magic hits failed the strict Stage1 validator.

Does not relax existing validation. Emits header / program metadata only.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf
TARGETS={"io-blk.so":0x2fb06,"fs-qnx6.so":0x7021a,
         "dumper":0x90843,"ksh":0xc0b8e,
         "devb-mmcsd-tegra3-devlite":0x151f95}
def diagnose(buf,offset):
    report={"offset":hex(offset),"magic_present":buf[offset:offset+4]==b"\x7fELF"}
    if offset+52>len(buf):
        report["reasons"]=["truncated_ELF_header"];return report
    ident=buf[offset:offset+16]
    typ,machine,version=struct.unpack_from("<HHI",buf,offset+16)
    entry,phoff,shoff,flags=struct.unpack_from("<IIII",buf,offset+24)
    ehsize,phentsize,phnum,shentsize,shnum,shstrndx=struct.unpack_from("<HHHHHH",buf,offset+40)
    report.update(elf_class=ident[4],endian=ident[5],ident_version=ident[6],
                  type=typ,machine=machine,version=version,entry=hex(entry),
                  phoff=phoff,phentsize=phentsize,phnum=phnum,
                  shoff=shoff,shentsize=shentsize,shnum=shnum,ehsize=ehsize)
    reasons=[]
    if ident[:7]!=b"\x7fELF\x01\x01\x01":reasons.append("not_32bit_little_endian_ELF_v1")
    if typ not in (1,2,3):reasons.append("invalid_type")
    if machine!=40:reasons.append("not_ARM")
    if version!=1:reasons.append("invalid_version")
    if ehsize!=52:reasons.append("invalid_ehsize")
    if phentsize!=32:reasons.append("invalid_phentsize")
    if not 0<phnum<=128:reasons.append("invalid_phnum")
    if phoff<52 or phoff+phnum*32>len(buf)-offset:reasons.append("program_table_unavailable")
    programs=[]
    if ident[:7]==b"\x7fELF\x01\x01\x01" and phentsize==32 and 0<phnum<=128 and phoff>=52 and phoff+phnum*32<=len(buf)-offset:
        for i in range(phnum):
            kind,off,va,pa,fs,ms,fl,align=struct.unpack_from("<IIIIIIII",buf,offset+phoff+i*32)
            row={"index":i,"type":hex(kind),"file_offset":hex(off),"filesz":fs,
                 "memsz":ms,"align":hex(align),"in_bounds":off+fs<=len(buf)-offset}
            if kind==1:
                row["load_size_valid"]=fs<=ms
                row["load_alignment_valid"]=align in (0,1) or (align&(align-1)==0 and (va-off)%align==0)
            programs.append(row)
    report["precheck_reasons"]=reasons
    report["programs"]=programs[:16]
    strict=[e for e in scan_elf(buf) if e["at"]==offset]
    report["existing_validator"]=strict[0] if strict else None
    return report
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--json",type=Path)
    a=parser.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    buf,end,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    output={"decoded_length":len(buf),"all_magic_count":buf.count(b"\x7fELF"),
            "targets":[{"candidate_name":name,**diagnose(buf,at)} for name,at in TARGETS.items()],
            "warning":"NAME association is a proximity hypothesis, not verified file ownership."}
    text=json.dumps(output,indent=2)+"\n";print(text,end="")
    if a.json:a.json.write_text(text)
if __name__=="__main__":main()
