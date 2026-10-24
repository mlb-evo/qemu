#!/usr/bin/env python3
"""Inspect bounded context around confirmed FPK1 Stage1/Stage2 boot references.

Coordinates are historical inner-image offsets (raw HSP member +0xc2).
Shows aligned hex/ASCII lines, zero-terminated strings and nearby uint32
values without saving raw firmware bytes.
"""
import argparse,json,struct,zipfile
from pathlib import Path

TARGETS={
    "stage1_ifs.img":[0x109de,0x10e48,0x794e0,0x79542,0x1765b4],
    "stage2_ifs.img":[0x18859,0x7a4df],
}
WINDOW=192

def display_lines(payload,lo,hi):
    out=[]
    for pos in range(lo,hi,16):
        sample=payload[pos:min(pos+16,hi)]
        out.append({"at":hex(pos),"hex":sample.hex(" "),
                    "ascii":"".join(chr(x) if 32<=x<127 else "." for x in sample)})
    return out

def around(payload,at):
    lo=max(0,(at-WINDOW)//16*16)
    hi=min(len(payload),((at+WINDOW+15)//16)*16)
    vicinity=payload[lo:hi]
    strings=[]
    for start,word in enumerate(vicinity.split(b"\x00")):
        # split yields strings but not offsets, so build them separately below
        pass
    cursor=lo
    while cursor<hi:
        if not 32<=payload[cursor]<127:
            cursor+=1
            continue
        end=cursor
        while end<hi and 32<=payload[end]<127:end+=1
        if end-cursor>=3:
            strings.append({"at":hex(cursor),"text":payload[cursor:end].decode("ascii","replace")})
        cursor=end
    # Show 32-bit words around the exact hit only, without assuming alignment.
    aligned=at&~3
    words=[]
    for p in range(max(0,aligned-32),min(len(payload)-4,aligned+64),4):
        words.append({"at":hex(p),"le":hex(struct.unpack_from("<I",payload,p)[0])})
    return {"reference":hex(at),"window":(hex(lo),hex(hi)),
            "ascii_runs":strings,"words32":words,"hex_dump":display_lines(payload,lo,hi)}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    reports={}
    with zipfile.ZipFile(args.archive) as z:
        for target,positions in TARGETS.items():
            matches=[p for p in z.namelist() if p.endswith("/"+target)]
            if len(matches)!=1:raise ValueError("Missing/ambiguous member: "+target)
            payload=z.read(matches[0])[0xc2:]
            reports[target]={
                "source_member":matches[0],
                "coordinates":"candidate inner image starts at raw member +0xc2",
                "windows":[around(payload,at) for at in positions]}
    rendered=json.dumps(reports,ensure_ascii=False,indent=2)+"\n"
    print(rendered,end="")
    if args.json:args.json.write_text(rendered)
if __name__=="__main__":main()
