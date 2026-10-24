#!/usr/bin/env python3
"""Compare ARM-code density against actual ELF boundaries in decoded Stage1.

Read-only and intentionally does not assign logical addresses to LZF suffixes.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

def density(buf,off,n=64):
    if off<0 or off+4*n>len(buf):return None
    words=struct.unpack_from("<"+"I"*n,buf,off)
    return {"always":sum((v>>28)==14 for v in words),
            "never":sum((v>>28)==15 for v in words),
            "branch_like":sum((v&0x0e000000)==0x0a000000 for v in words)}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Stage1 ambiguous")
        raw=z.read(names[0]);inner=raw[0xc2:]
    rows=[]
    for start in (0x1318fc,0x18d9fe):
        decoded,stop,err=decode(inner[:0x1f6ffb],start)
        elfs=scan_elf(decoded)
        valid=[e for e in elfs if e["strict_elf_valid"]]
        markers=[]
        for e in valid:
            pos=e["at"]
            if pos+52>len(decoded):continue
            entry=struct.unpack_from("<I",decoded,pos+24)[0]
            phoff=struct.unpack_from("<I",decoded,pos+28)[0]
            n=struct.unpack_from("<H",decoded,pos+44)[0]
            loads=[]
            for i in range(min(n,128)):
                at=pos+phoff+32*i
                typ,fileoff,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from("<IIIIIIII",decoded,at)
                if typ==1:
                    in_segment=vaddr<=entry<vaddr+memsz
                    relative=pos+fileoff+(entry-vaddr) if in_segment and entry-vaddr<filesz else None
                    loads.append({"vaddr":hex(vaddr),"filesz":filesz,"memsz":memsz,
                                  "entry_in_load":in_segment,
                                  "entry_file_offset":hex(relative) if relative is not None else None,
                                  "entry_density":density(decoded,relative) if relative is not None else None})
            markers.append({"elf_decoded_offset":hex(pos),"entry":hex(entry),
                            "entry_in_pt_load":any(x["entry_in_load"] for x in loads),
                            "pt_loads":loads})
        rows.append({"suffix_start":hex(start),"decode_error":err,
                     "strict_elf_count":len(valid),"elf_entry_analysis":markers})
    out=json.dumps({"results":rows,"warning":"ELF entry points mapped only inside their own PT_LOAD; never identify arbitrary suffix +0x6b98 with Stage1 logical entry."},indent=2)+"\n"
    print(out,end="")
    if a.json:a.json.write_text(out)
if __name__=="__main__":main()
