#!/usr/bin/env python3
"""Profile recurring Stage1 byte patterns and transitions (read-only).

Do not infer compression or encryption solely from entropy. All offsets are
relative to HSP member +0xc2, matching other FPK1 research tools.
"""
import argparse, json, math, zipfile
from collections import Counter
from pathlib import Path

NAMES=("stage1_ifs.img","stage1_RECOVERY_ifs.img")
PATTERNS=(b"\xe0\xff\x00",b"imagefs",b"\xeb\x7e\xff\x00")
WINDOW=4096

def entropy(block):
    if not block:return 0.0
    hist=Counter(block)
    total=len(block)
    return round(-sum((v/total)*math.log2(v/total) for v in hist.values()),4)

def profile(data):
    windows=[]
    for start in range(0,len(data),WINDOW):
        block=data[start:start+WINDOW]
        patterns={p.hex():block.count(p) for p in PATTERNS}
        windows.append({"offset":hex(start),"size":len(block),
                        "entropy":entropy(block),"zeros":block.count(0),
                        "ff":block.count(255),"printable":sum(32<=b<=126 for b in block),
                        "pattern_counts":patterns})
    run=[]
    needle=PATTERNS[0]
    at=0
    while (at:=data.find(needle,at))>=0:
        count=0
        while data[at+3*count:at+3*count+3]==needle:count+=1
        if count>=4:
            run.append({"start":hex(at),"triples":count,"bytes":3*count})
            at+=3*count
        else:at+=1
    ranked=sorted(windows,key=lambda x:x["pattern_counts"][needle.hex()],reverse=True)[:12]
    return {"length":len(data),"pattern_triple_runs":run[:64],
            "total_pattern_triple_runs":len(run),
            "top_windows_by_pattern":ranked,
            "windows_0x0_to_0x20000":windows[:32],
            "windows_0x76000_to_0x82000":[w for w in windows if 0x76000<=int(w["offset"],16)<0x82000],
            "window_summary":{"count":len(windows),
                "high_entropy_over_7_5":sum(w["entropy"]>7.5 for w in windows),
                "low_entropy_under_3":sum(w["entropy"]<3 for w in windows)}}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    report={}
    with zipfile.ZipFile(args.archive) as z:
        for name in NAMES:
            matches=[n for n in z.namelist() if n.endswith("/"+name)]
            if len(matches)!=1:raise ValueError("Missing or ambiguous "+name)
            raw=z.read(matches[0])
            if raw[:3]!=b"HSP":raise ValueError("Unexpected HSP envelope")
            report[name]=profile(raw[0xc2:])
    result=json.dumps(report,indent=2)+"\n"
    print(result,end="")
    if args.json:args.json.write_text(result)
if __name__=="__main__":main()
