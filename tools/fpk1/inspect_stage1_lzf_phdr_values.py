#!/usr/bin/env python3
"""Inspect decoded Stage1 LZF ELF32 ARM program header values.

Read-only, no firmware extraction. Report PT_LOAD p_filesz, p_memsz, p_offset,
p_align, and whether filesz <= memsz; do not mistake presence for validity.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import STARTS, decode

def analyze_elf(buf,off):
    if off+52>len(buf) or buf[off:off+7]!=b"\x7fELF\x01\x01\x01":return None
    machine,version=struct.unpack_from("<HI",buf,off+18)
    phoff=struct.unpack_from("<I",buf,off+28)[0]
    ehsize,phentsize,phnum=struct.unpack_from("<HHH",buf,off+40)
    if not (machine==40 and version==1 and ehsize==52 and phentsize==32 and 0<phnum<=128 and phoff>=52 and off+phoff+phnum*32<=len(buf)):return None
    programs=[]
    for n in range(phnum):
        kind,fileoff,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from("<IIIIIIII",buf,off+phoff+n*32)
        if kind not in (0,1,2,3,4,6,7,0x6474e550,0x6474e551,0x6474e552):type_label="unknown"
        else:type_label={1:"PT_LOAD",2:"PT_DYNAMIC",3:"PT_INTERP",4:"PT_NOTE",6:"PT_PHDR",7:"PT_TLS"}.get(kind,"other")
        programs.append({"type":hex(kind),"type_name":type_label,"file_offset":hex(fileoff),
                         "vaddr":hex(vaddr),"paddr":hex(paddr),"filesz":filesz,"memsz":memsz,
                         "flags":hex(flags),"align":hex(align),
                         "file_fits_decoded":fileoff+filesz<=len(buf)-off,
                         "filesz_le_memsz":filesz<=memsz,
                         "p_align_power_of_two":align in (0,1) or (align&(align-1))==0})
    return {"decoded_offset":hex(off),"header_phnum":phnum,"phoff":hex(phoff),
            "programs":programs}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        members=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Missing/ambiguous Stage1")
        data=z.read(members[0])[0xc2:]
    rows=[]
    for start in STARTS:
        decoded,stop,error=decode(data,start)
        elfs=[]
        p=0
        while (p:=decoded.find(b"\x7fELF",p))!=-1:
            e=analyze_elf(decoded,p)
            if e:elfs.append(e)
            p+=4
        rows.append({"candidate_start":hex(start),"stop":hex(stop),"error":error,"elfs":elfs[:20]})
    report={"note":"LZF suffix candidates; ELF header structural checks do not guarantee image integrity",
            "starts":rows}
    out=json.dumps(report,indent=2)+"\n"
    print(out,end="")
    if args.json:args.json.write_text(out)
if __name__=="__main__":main()
