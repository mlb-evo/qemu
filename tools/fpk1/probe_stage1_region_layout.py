#!/usr/bin/env python3
"""Compare Stage1 primary/recovery container region boundaries and encoded data.

Read-only, no heuristic decompression. Offsets in candidate inner (HSP +0xc2).
Reports per-window entropy, bytes, runs and reference neighborhoods.
"""
import argparse, hashlib, json, math, struct, zipfile
from collections import Counter
from pathlib import Path

NAMES=("stage1_ifs.img","stage1_RECOVERY_ifs.img")
WINDOWS=(0,0x200,0x250,0x7f0,0x800,0x808,0x820,0x900,0x1000,0x2000,
         0xe500,0x10bc0,0x10c00,0x78000,0x79000,0x79400,0x79800,0x80000)
BLOCK_SIZES=(256,512,1024,2048,4096,8192,16384)
def entropy(data):
    n=len(data)
    return round(-sum((v/n)*math.log2(v/n) for v in Counter(data).values()),4) if n else None
def run_stats(buf):
    return {"zeros":buf.count(0),"ff":buf.count(255),
            "printable_ascii":sum(32<=c<127 for c in buf),
            "entropy":entropy(buf)}
def inspect(data):
    declared=struct.unpack_from("<I",data)[0]
    result={"size":len(data),"length_field":declared,
            "qnx_magic_0x808":data[0x808:0x80c].hex(),
            "imagefs_marker_offsets":[],
            "windows":[],"block_summaries":{}}
    for at in WINDOWS:
        if at>=len(data):continue
        buf=data[at:at+256]
        result["windows"].append({"start":hex(at),"sha256":hashlib.sha256(buf).hexdigest(),
                                  "first_32":buf[:32].hex(),"stats":run_stats(buf)})
    for block in BLOCK_SIZES:
        begin=0x800
        sectors=[]
        for at in range(begin,min(begin+block*16,len(data)),block):
            b=data[at:at+block]
            sectors.append({"offset":hex(at),"stats":run_stats(b),
                            "first_16":b[:16].hex()})
        result["block_summaries"][str(block)]=sectors
    for tag in (b"imagefs",b"#imagefs"):
        hits=[]
        pos=0
        while (pos:=data.find(tag,pos))>=0:
            hits.append(hex(pos));pos+=1
            if len(hits)>=32:break
        result["imagefs_marker_offsets"].extend(hits)
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        images={}
        for name in NAMES:
            members=[n for n in z.namelist() if n.endswith("/"+name)]
            if len(members)!=1:raise ValueError("Missing or ambiguous "+name)
            raw=z.read(members[0])
            if raw[:3]!=b"HSP":raise ValueError("HSP expected")
            images[name]=raw[0xc2:]
    report={"coordinate_system":"HSP raw member + 0xc2",
            "images":{k:inspect(v) for k,v in images.items()}}
    a_data,b_data=[images[k] for k in NAMES]
    comparisons=[]
    for at in WINDOWS:
        if at>=min(len(a_data),len(b_data)):continue
        a_buf=a_data[at:at+256];b_buf=b_data[at:at+256]
        comparisons.append({"start":hex(at),"different_bytes":sum(x!=y for x,y in zip(a_buf,b_buf)),
                            "identical":a_buf==b_buf})
    report["primary_recovery_windows"]=comparisons
    text=json.dumps(report,indent=2)+"\n"
    print(text,end="")
    if a.json:a.json.write_text(text)
if __name__=="__main__":main()
