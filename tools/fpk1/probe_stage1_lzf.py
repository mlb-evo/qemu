#!/usr/bin/env python3
"""Read-only LZF stream probe for primary FPK1 Stage1 image.

Decode bounded candidate streams in memory, report ELF32 ARM validation and
QNX imagefs markers; never export or commit decoded proprietary bytes.
LZF: literal ctrl<32 copies ctrl+1 bytes; reference length=(ctrl>>5)+2,
extends by next byte for length code 7, offset=((ctrl&31)<<8)+byte+1.
"""
import argparse,json,struct,zipfile
from pathlib import Path

LIMIT=64*1024*1024
STARTS=(0,0x800,0x808,0x810,0x820,0x900,0x1000,0x2000,0xe000,0xe100,0xe500,0x10bc0)

def decode(src,limit=LIMIT):
    out=bytearray()
    p=0
    while p<len(src):
        ctl=src[p];p+=1
        if ctl<32:
            n=ctl+1
            if p+n>len(src):raise ValueError(f"truncated literal at {p-1:#x}")
            if len(out)+n>limit:raise ValueError("output size limit")
            out.extend(src[p:p+n]);p+=n
        else:
            n=ctl>>5
            if n==7:
                if p>=len(src):raise ValueError("truncated long match")
                n+=src[p];p+=1
            if p>=len(src):raise ValueError("truncated match offset")
            distance=((ctl&31)<<8)+src[p]+1;p+=1
            n+=2
            if distance>len(out):raise ValueError(f"backreference before stream start at {p:#x} distance {distance} out {len(out)}")
            if len(out)+n>limit:raise ValueError("output size limit")
            # LZF references may overlap, e.g. E0 FF 00 repeats previous byte.
            if distance==1:
                out.extend(bytes([out[-1]])*n)
            elif distance>=n:
                out.extend(out[len(out)-distance:len(out)-distance+n])
            else:
                for _ in range(n):out.append(out[-distance])
    return bytes(out)

def elf_candidates(data):
    candidates=[]
    p=0
    while (p:=data.find(b"\x7fELF",p))>=0:
        if p+52<=len(data):
            h=data[p:p+52]
            good_ident=h[:7]==b"\x7fELF\x01\x01\x01"
            machine=struct.unpack_from("<H",h,18)[0]
            version=struct.unpack_from("<I",h,20)[0]
            ehsize=struct.unpack_from("<H",h,40)[0]
            phentsize=struct.unpack_from("<H",h,42)[0]
            candidates.append({"at":hex(p),"machine":machine,"version":version,
                               "ehsize":ehsize,"phentsize":phentsize,
                               "valid_elf32_arm":good_ident and machine==40 and version==1
                                                  and ehsize==52 and phentsize in (0,32)})
        p+=4
    return candidates[:100]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    ap.add_argument("--starts",help="comma-separated candidate stream offsets in inner image (e.g. 0x800,0x1000)")
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Stage1 not uniquely found")
        raw=z.read(members[0])
        if raw[:3]!=b"HSP":raise ValueError("HSP wrapper missing")
        data=raw[0xc2:]
    starts=[int(x,0) for x in args.starts.split(",")] if args.starts else STARTS
    results=[]
    for start in starts:
        if not 0<=start<len(data):continue
        try:
            decoded=decode(data[start:])
            elfs=elf_candidates(decoded)
            results.append({"start":hex(start),"success":True,"decoded_length":len(decoded),
                            "decoded_first_32":decoded[:32].hex(),
                            "elf_magic_count":len(elfs),"valid_elf32_arm_count":sum(e["valid_elf32_arm"] for e in elfs),
                            "elf_examples":elfs[:12],
                            "imagefs_magic_offsets":[]})
            item=results[-1]
            for needle in (b"imagefs\x04",b"#imagefs"):
                cursor=0
                while (cursor:=decoded.find(needle,cursor))>=0:
                    item["imagefs_magic_offsets"].append({"at":hex(cursor),"magic":needle.hex()})
                    cursor+=1
                    if len(item["imagefs_magic_offsets"])>=12:break
        except ValueError as exc:
            results.append({"start":hex(start),"success":False,"error":str(exc)})
    report={"member":members[0],"offset_coordinates":"Stage1 inner bytes = HSP raw member +0xc2",
            "codec":"LZF candidate", "max_decoded_bytes":LIMIT,"probes":results}
    encoded=json.dumps(report,indent=2)+"\n"
    print(encoded,end="")
    if args.json:args.json.write_text(encoded)
if __name__=="__main__":main()
