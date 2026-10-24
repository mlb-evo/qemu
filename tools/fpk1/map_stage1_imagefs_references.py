#!/usr/bin/env python3
"""Classify Stage1 boot-reference bytes against QNX imagefs catalog candidates.

Inspect archive in memory; no proprietary blobs are saved. Validates imagefs
header and record structure before mapping an offset to a regular-file extent.
A string occurrence alone is not evidence that a file is decoded or executed.
"""
import argparse
import json
import struct
import zipfile
from pathlib import Path

TARGETS=(0x794d7,0x794e0,0x79515,0x79542,0x79558,0x795c1)
MAGIC=b"imagefs\x04"
MAX_ENTRIES=10000
MAX_SCAN=64*1024

def u32(raw,pos):
    return struct.unpack_from("<I",raw,pos)[0]

def parse_candidate(raw,base):
    if base+24>len(raw):raise ValueError("truncated header")
    logical,data_start,dir_off=struct.unpack_from("<III",raw,base+8)
    if not 24<=dir_off<MAX_SCAN:raise ValueError("bad directory offset")
    if not dir_off<data_start<=logical:raise ValueError("inconsistent declared layout")
    pos=base+dir_off
    if pos>=len(raw):raise ValueError("directory outside stored region")
    rows=[]
    seen_terminator=False
    for _ in range(MAX_ENTRIES):
        if pos+2>len(raw):break
        length=struct.unpack_from("<H",raw,pos)[0]
        if length==0:
            seen_terminator=True
            break
        if length<24 or length>4096 or length%4 or pos+length>len(raw) or (pos+length-base)>data_start:
            raise ValueError("invalid record boundary")
        mode=u32(raw,pos+8)
        regular=(mode&0xf000)==0x8000
        name_at=32 if regular else 24
        if length<=name_at:raise ValueError("short name")
        name=raw[pos+name_at:pos+length].split(b"\x00",1)[0]
        if not name or b"/../" in name or name.startswith(b"/") or any(c<32 for c in name):
            raise ValueError("invalid filename bytes")
        row={"name":name.decode("utf8","replace"),"mode":oct(mode),"record_at":hex(pos)}
        if regular:
            offset,size=struct.unpack_from("<II",raw,pos+24)
            if offset<data_start or offset+size>logical:
                raise ValueError("file extent outside logical image")
            row.update(data_start=hex(base+offset),data_end=hex(base+offset+size),
                       size=size,stored_in_bounds=base+offset+size<=len(raw))
        rows.append(row)
        pos+=length
    if not seen_terminator or not rows:raise ValueError("no terminating directory")
    return {"base":hex(base),"logical_size":logical,"data_start":data_start,
            "directory_offset":dir_off,"entries":len(rows),
            "regular_files":sum("size" in r for r in rows),
            "catalog_end":hex(pos),
            "files":rows}

def classify(files):
    out=[]
    for target in TARGETS:
        matched=[]
        for candidate in files:
            base=int(candidate["base"],16)
            if base<=target<base+candidate["data_start"]:
                matched.append({"base":candidate["base"],"region":"imagefs metadata"})
            for f in candidate["files"]:
                if "size" in f and int(f["data_start"],16)<=target<int(f["data_end"],16):
                    matched.append({"base":candidate["base"],"region":"regular file extent",
                                    "path":f["name"],"file_relative":hex(target-int(f["data_start"],16)),
                                    "stored_in_bounds":f["stored_in_bounds"]})
        out.append({"target":hex(target),"matches":matched,
                    "note":"unmapped does not rule out compressed/encoded backing" if not matched else None})
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Missing or ambiguous Stage1 image")
        raw=z.read(members[0])[0xc2:]
    candidates=[]
    rejected=[]
    pos=0
    while (pos:=raw.find(MAGIC,pos))>=0:
        try:candidates.append(parse_candidate(raw,pos))
        except ValueError as e:rejected.append({"at":hex(pos),"reason":str(e)})
        pos+=1
    report={"member":members[0],"coordinate_system":"Stage1 candidate inner: raw member +0xc2",
            "candidate_headers":[{"base":c["base"],"logical_size":c["logical_size"],
                                  "data_start":c["data_start"],"entries":c["entries"],
                                  "regular_files":c["regular_files"],
                                  "catalog_end":c["catalog_end"]} for c in candidates],
            "rejected_headers":rejected,
            "references":classify(candidates),
            "candidate_file_paths":[{"imagefs_base":c["base"],"paths":[f["name"] for f in c["files"]]}
                                    for c in candidates]}
    encoded=json.dumps(report,indent=2)+"\n"
    print(encoded,end="")
    if args.json:args.json.write_text(encoded)

if __name__=="__main__":
    main()
