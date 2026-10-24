#!/usr/bin/env python3
"""Inventory strict decoded Stage1 ELF headers, load segments and name clues.

Read-only, never writes decoded executable bytes.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

def printable(raw):
    return "".join(chr(x) if 32<=x<127 else "." for x in raw)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    ap.add_argument("--start",type=lambda x:int(x,0),default=0x1318fc)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    src=raw[0xc2:]
    out,stop,error=decode(src[:0x1f6ffb],args.start)
    strict=[e for e in scan_elf(out) if e["strict_elf_valid"]]
    items=[]
    for e in strict:
        at=e["at"]
        etype,machine=struct.unpack_from("<HH",out,at+16)
        entry,phoff=struct.unpack_from("<II",out,at+24)
        phnum=struct.unpack_from("<H",out,at+44)[0]
        loads=[];entry_file=None;max_file_end=0
        for j in range(phnum):
            typ,fo,va,pa,fs,ms,flags,align=struct.unpack_from("<IIIIIIII",out,at+phoff+j*32)
            if typ!=1:continue
            max_file_end=max(max_file_end,fo+fs)
            if va<=entry<va+ms and entry-va<fs:
                entry_file=at+fo+entry-va
            loads.append({"file_offset":hex(fo),"vaddr":hex(va),"filesz":fs,
                          "memsz":ms,"flags":hex(flags),"align":hex(align)})
        # Neighboring text is a clue, not necessarily the true catalog name.
        before=out[max(0,at-96):at]
        after=out[at+max_file_end:at+max_file_end+96]
        entry_bytes=out[entry_file:entry_file+16].hex() if entry_file is not None else None
        items.append({"elf_at":hex(at),"type":{2:"ET_EXEC",3:"ET_DYN",1:"ET_REL"}.get(etype,hex(etype)),
                      "entry":hex(entry),"entry_file_offset":hex(entry_file) if entry_file is not None else None,
                      "entry_bytes":entry_bytes,"load_segments":loads,
                      "max_file_end":max_file_end,
                      "name_clue_before":printable(before[-64:]),
                      "name_clue_after":printable(after[:64])})
    report={"candidate_encoded_start":hex(args.start),"encoded_stop":hex(stop),
            "decode_error":error,"strict_elf_count":len(items),"elfs":items,
            "caution":"Name clues are raw neighboring text, not verified imagefs catalog entries."}
    encoded=json.dumps(report,indent=2)+"\n"
    print(encoded,end="")
    if args.json:args.json.write_text(encoded)
if __name__=="__main__":main()
