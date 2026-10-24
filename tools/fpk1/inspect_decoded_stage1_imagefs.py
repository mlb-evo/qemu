#!/usr/bin/env python3
"""Inspect decoded LZF Stage1 suffix for imagefs header/catalog evidence.

In-memory, read-only, no binaries exported. Imagefs candidates require valid
header values and terminated records, not just a matching string.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,STARTS,scan_elf

def inspect_imagefs(buf,base):
    if base+24>len(buf):return {"reason":"short header"}
    version_ok=buf[base:base+8]==b"imagefs\x04"
    if not version_ok:return {"reason":"not imagefs v4"}
    total,data_start,dir_off=struct.unpack_from("<III",buf,base+8)
    row={"base":hex(base),"logical_size":total,"data_start":data_start,"directory":dir_off}
    if not 24<=dir_off<data_start<=total:
        return dict(row,reason="invalid header extents")
    if dir_off>262144 or base+dir_off>=len(buf):
        return dict(row,reason="directory not available")
    pos=base+dir_off
    files=[]
    for _ in range(10000):
        if pos+2>len(buf):return dict(row,reason="truncated catalog")
        n=struct.unpack_from("<H",buf,pos)[0]
        if n==0:return dict(row,reason=None,count=len(files),sample=files[:25],
                            catalog_end=hex(pos))
        if n<24 or n>4096 or n%4 or pos+n>len(buf) or pos+n>base+data_start:
            return dict(row,reason="bad record",count=len(files),record_at=hex(pos))
        mode=struct.unpack_from("<I",buf,pos+8)[0]
        name_start=32 if mode&0xf000==0x8000 else 24
        if n<=name_start:return dict(row,reason="short record")
        name=buf[pos+name_start:pos+n].split(b"\0",1)[0]
        if not name or name.startswith(b"/") or any(c<32 for c in name):
            return dict(row,reason="invalid path",count=len(files))
        item={"name":name.decode("utf8","replace"),"mode":oct(mode)}
        if name_start==32:
            off,size=struct.unpack_from("<II",buf,pos+24)
            item.update(offset=off,size=size,extent_in_decoded=base+off+size<=len(buf))
            if off<data_start or off+size>total:return dict(row,reason="invalid file extent")
        files.append(item)
        pos+=n
    return dict(row,reason="record limit",count=len(files))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--start",type=lambda x:int(x,0),default=0x1318fc)
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        m=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(m)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(m[0])
        if raw[:3]!=b"HSP":raise ValueError("Expected HSP")
        src=raw[0xc2:]
    if not 0<=a.start<len(src):raise ValueError("invalid start")
    decoded,stop,error=decode(src,a.start)
    hits=[]
    p=0
    while (p:=decoded.find(b"imagefs",p))!=-1:
        hits.append(inspect_imagefs(decoded,p))
        p+=7
        if len(hits)>=100:break
    valid_elf=scan_elf(decoded)
    report={"start":hex(a.start),"encoded_stop":hex(stop),
            "physical_inner_end":hex(len(src)),
            "encoded_bytes_remaining":len(src)-stop,
            "last_raw_32":src[max(0,stop-32):stop].hex(),
            "decode_error":error,"decoded_length":len(decoded),
            "imagefs_text_matches":len(hits),
            "imagefs_header_candidates":hits,
            "elf_candidates_returned":len(valid_elf),
            "strict_elf_valid":sum(x["strict_elf_valid"] for x in valid_elf),
            "caution":"Valid suffix decoding does not prove correct compressed stream start or full imagefs."}
    out=json.dumps(report,indent=2)+"\n"
    print(out,end="")
    if a.json:a.json.write_text(out)
if __name__=="__main__":main()
