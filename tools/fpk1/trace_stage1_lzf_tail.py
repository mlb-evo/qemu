#!/usr/bin/env python3
"""Analyze the physical end of FPK1 Stage1's candidate LZF suffix.

Reports exact token boundaries, trailing padding, and possible stream end
positions; does not assume EOF is a valid compression terminator.
"""
import argparse,json,zipfile
from pathlib import Path

STARTS=(0x1318fc,0x18d9fe,0x194216,0x1c14f5)
def trace(src,start,cap=32*1024*1024):
    p=start
    size=0
    recent=[]
    last_nonzero=None
    last_token_end=start
    while p<len(src):
        token=p
        ctl=src[p];p+=1
        if ctl<32:
            count=ctl+1
            if p+count>len(src):
                return {"error":"truncated_literal","failed_token_start":hex(token),
                        "control":hex(ctl),"requested_literal_bytes":count,
                        "remaining":len(src)-p,"last_complete_token_end":hex(last_token_end),
                        "last_tokens":recent[-12:],"decoded_bytes":size}
            raw=src[p:p+count]
            if any(raw):last_nonzero=p+max(i for i,v in enumerate(raw) if v)
            p+=count;size+=count;kind="literal"
        else:
            count=ctl>>5
            if count==7:
                if p>=len(src):return {"error":"truncated_long_match","token_start":hex(token)}
                count+=src[p];p+=1
            if p>=len(src):return {"error":"truncated_distance","token_start":hex(token)}
            distance=((ctl&31)<<8)+src[p]+1;p+=1
            count+=2;kind="reference"
            if distance>size:return {"error":"invalid_reference","token_start":hex(token),
                                      "distance":distance,"decoded_bytes":size}
            size+=count
        if size>cap:return {"error":"output_cap","decoded_bytes":size,"token_start":hex(token)}
        recent.append({"start":hex(token),"end":hex(p),"type":kind,
                       "out_size":size})
        if len(recent)>16:recent.pop(0)
        last_token_end=p
    return {"error":None,"decoded_bytes":size,"last_complete_token_end":hex(p),
            "last_tokens":recent[-12:]}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("archive",type=Path);a.add_argument("--json",type=Path)
    args=a.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Stage1 ambiguous")
        raw=z.read(names[0])
        if raw[:3]!=b"HSP":raise ValueError("HSP expected")
        src=raw[0xc2:]
    last_nonzero=max((i for i,c in enumerate(src) if c),default=-1)
    result={"inner_size":hex(len(src)),"last_nonzero_at":hex(last_nonzero),
            "tail_64":src[-64:].hex(),"suffix_starts":[]}
    for start in STARTS:
        result["suffix_starts"].append({"start":hex(start),**trace(src,start)})
    result["caution"]="LZF framing not validated; last complete token != documented block boundary."
    out=json.dumps(result,indent=2)+"\n"
    print(out,end="")
    if args.json:args.json.write_text(out)
if __name__=="__main__":main()
