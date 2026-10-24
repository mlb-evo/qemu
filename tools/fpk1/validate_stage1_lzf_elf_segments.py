#!/usr/bin/env python3
"""Validate decoded ELF segments near Stage1 LZF run boundaries.

Local seeded decoding is forensic evidence only, not a recovery of full IFS.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from probe_stage1_lzf_local import PAT,decode_prefix

def check_elf(data,off):
    if off+52>len(data):return None
    h=data[off:off+52]
    if h[:7]!=b"\x7fELF\x01\x01\x01":return None
    typ,machine,version=struct.unpack_from("<HHI",h,16)
    entry,phoff,shoff,flags=struct.unpack_from("<IIII",h,24)
    ehsize,phentsize,phnum,shentsize,shnum=struct.unpack_from("<HHHHH",h,40)
    header_ok=(machine==40 and version==1 and ehsize==52 and
               phentsize==32 and 0<phnum<=128 and phoff>=52 and
               phoff+phnum*32<=len(data)-off)
    segments=[]
    if header_ok:
        for i in range(phnum):
            t,fo,vaddr,paddr,filesz,memsz,pflags,align=struct.unpack_from("<IIIIIIII",data,off+phoff+i*32)
            segments.append({"type":t,"file_offset":hex(fo),"file_size":filesz,
                             "memory_size":memsz,"alignment":align,
                             "stored_extent_available":fo+filesz<=len(data)-off,
                             "memory_extent_plausible":filesz<=memsz,
                             "alignment_power_of_two":align==0 or align&(align-1)==0})
    load=[s for s in segments if s["type"]==1]
    return {"decoded_at":off,"e_type":typ,"e_machine":machine,"entry":hex(entry),
            "phoff":phoff,"phnum":phnum,"header_ok":header_ok,
            "load_segments":len(load),
            "all_file_extents_available":bool(segments) and all(s["stored_extent_available"] for s in segments),
            "all_segment_sizes_plausible":bool(segments) and all(s["memory_extent_plausible"] for s in segments),
            "segments":segments[:16]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        paths=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(paths)!=1:raise ValueError("Primary Stage1 not unique")
        data=z.read(paths[0])[0xc2:]
    rows=[];pos=0
    while (pos:=data.find(PAT,pos))>=0:
        at=pos
        while data[pos:pos+3]==PAT:pos+=3
        count=(pos-at)//3
        if count<4:pos=at+1;continue
        decoded,consumed,error=decode_prefix(data[at:at+65536])
        hit=decoded.find(b"\x7fELF")
        candidate=check_elf(decoded,hit) if hit>=0 else None
        if candidate and candidate["header_ok"]:
            rows.append({"run_start":hex(at),"run_triplets":count,
                         "consumed_encoded_bytes":consumed,"decoded_size":len(decoded),
                         "decode_error":error,"elf":candidate})
    report={"method":"bounded seeded local LZF decode, not independently verified original file",
            "valid_program_header_candidates":sum(r["elf"]["header_ok"] for r in rows),
            "with_load_segments":sum(r["elf"]["load_segments"]>0 for r in rows),
            "with_all_extents_in_local_decode":sum(r["elf"]["all_file_extents_available"] for r in rows),
            "candidates":rows}
    out=json.dumps(report,indent=2)+"\n"
    print(out,end="")
    if a.json:a.json.write_text(out)
if __name__=="__main__":main()
