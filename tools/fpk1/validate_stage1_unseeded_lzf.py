#!/usr/bin/env python3
"""Validate unseeded Stage1 LZF candidates and ELF program segment extents.

Important: candidates may start in the middle of a true LZF stream.
No proprietary payloads are written.
"""
import argparse,json,struct,zipfile
from pathlib import Path

STARTS=(0x1318fc,0x131910,0x131911,0x18d9fe,0x18d9ff,0x194216,0x1c14f5,0x1c14f6)
LIMIT=16*1024*1024

def decode(src,start,limit=LIMIT):
    out=bytearray();p=start
    while p<len(src):
        ctl=src[p];p+=1
        if ctl<32:
            n=ctl+1
            if p+n>len(src):return out,p,"truncated literal"
            if len(out)+n>limit:return out,p,"output limit"
            out.extend(src[p:p+n]);p+=n
        else:
            n=ctl>>5
            if n==7:
                if p>=len(src):return out,p,"truncated length"
                n+=src[p];p+=1
            if p>=len(src):return out,p,"truncated offset"
            dist=((ctl&31)<<8)+src[p]+1;p+=1;n+=2
            if dist>len(out):return out,p,"invalid backreference"
            if len(out)+n>limit:return out,p,"output limit"
            if dist==1:out.extend(bytes([out[-1]])*n)
            elif dist>=n:out.extend(out[-dist:-dist+n])
            else:
                for _ in range(n):out.append(out[-dist])
    return out,p,None

def scan_elf(buf):
    """Conservative ELF32 ARM check; validate PHDR semantics, not merely bounds."""
    out=[];at=0
    allowed={0,1,2,3,4,6,7,0x6474e550,0x6474e551,0x6474e552}
    while (at:=buf.find(b"\\x7fELF",at))>=0:
        if at+52<=len(buf):
            ident=buf[at:at+16]
            typ,machine,version=struct.unpack_from("<HHI",buf,at+16)
            entry,phoff,shoff,flags=struct.unpack_from("<IIII",buf,at+24)
            ehsize,entsize,n,shentsize,shnum,shstrndx=struct.unpack_from("<HHHHHH",buf,at+40)
            header_ok=(ident[:7]==b"\\x7fELF\\x01\\x01\\x01" and
                ident[7:16]==b"\\x00"*9 and typ in (1,2,3) and machine==40 and version==1 and
                ehsize==52 and entsize==32 and 0<n<=128 and phoff>=52 and
                phoff+n*32<=len(buf)-at)
            if header_ok:
                segments=[];bad=[]
                for i in range(n):
                    kind,off,vaddr,paddr,filesz,memsz,pflags,align=struct.unpack_from(
                        "<IIIIIIII",buf,at+phoff+i*32)
                    available=off+filesz<=len(buf)-at
                    is_load=kind==1
                    load_valid=(not is_load or (filesz<=memsz and
                        (align in (0,1) or ((align&(align-1))==0 and (vaddr-off)%align==0))))
                    known_type=kind in allowed
                    if not known_type:bad.append(f"unknown_program_type:{kind:#x}")
                    if is_load and not load_valid:bad.append(f"invalid_PT_LOAD:{i}")
                    if not available:bad.append(f"program_extent_missing:{i}")
                    segments.append({"type":kind,"file_offset":off,"file_size":filesz,
                        "memory_size":memsz,"stored_extent_available":available,
                        "load_semantics_valid":load_valid})
                loads=[x for x in segments if x["type"]==1]
                if not loads:bad.append("no_PT_LOAD")
                out.append({"at":at,"phnum":n,"pt_load":len(loads),
                    "all_pt_load_present":bool(loads) and all(x["stored_extent_available"] for x in loads),
                    "all_pt_load_size_ok":bool(loads) and all(x["load_semantics_valid"] for x in loads),
                    "strict_elf_valid":not bad,"rejection_reasons":bad[:12],
                    "max_load_file_end":max((x["file_offset"]+x["file_size"] for x in loads),default=0)})
        at+=4
    return out[:50]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        data=z.read(names[0])[0xc2:]
    rows=[]
    for start in STARTS:
        buf,end,error=decode(data,start)
        elfs=scan_elf(buf)
        rows.append({"start":hex(start),"encoded_end":hex(end),"encoded_consumed":end-start,
                     "decoded_size":len(buf),"decode_error":error,
                     "elf_valid_count":len(elfs),
                     "elf_with_complete_loads":sum(e["all_pt_load_present"] and e["all_pt_load_size_ok"] for e in elfs),
                     "strict_valid_elf_count":sum(e["strict_elf_valid"] for e in elfs),
                     "elfs":elfs[:12]})
    result={"note":"Empty-history LZF suffix decoding; exact stream boundaries remain unverified",
            "starts":rows}
    txt=json.dumps(result,indent=2)+"\n"
    print(txt,end="")
    if a.json:a.json.write_text(txt)
if __name__=="__main__":main()
