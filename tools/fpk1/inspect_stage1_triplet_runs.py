#!/usr/bin/env python3
"""Profile Stage1 E0 FF 00 runs and neighboring bytes without codec guesses.

Read-only. Reports run lengths and boundary contexts (short hex samples),
relative to candidate inner Stage1 bytes at HSP member +0xc2.
"""
import argparse,collections,json,zipfile
from pathlib import Path
PAT=b"\xe0\xff\x00"
FILES=("stage1_ifs.img","stage1_RECOVERY_ifs.img")
def inspect(buf):
    pos=0
    rows=[]
    while (pos:=buf.find(PAT,pos))>=0:
        start=pos
        while buf[pos:pos+3]==PAT:pos+=3
        count=(pos-start)//3
        if count>=4:
            rows.append({"start":hex(start),"end":hex(pos),"triples":count,
                         "start_mod_16":start%16,"start_mod_512":start%512,
                         "before_24":buf[max(0,start-24):start].hex(),
                         "after_24":buf[pos:pos+24].hex()})
        else:pos=start+1
    hist=collections.Counter(row["triples"] for row in rows)
    return {"total_runs":len(rows),"total_run_bytes":sum(row["triples"]*3 for row in rows),
            "run_lengths":dict(sorted(hist.items())),
            "longest_runs":sorted(rows,key=lambda x:x["triples"],reverse=True)[:24],
            "runs_near_0x79000":[r for r in rows if abs(int(r["start"],16)-0x79000)<0x3000],
            "start_mod_16_hist":dict(sorted(collections.Counter(r["start_mod_16"] for r in rows).items())),
            "start_mod_512_hist_top":collections.Counter(r["start_mod_512"] for r in rows).most_common(16)}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    result={}
    with zipfile.ZipFile(a.archive) as z:
        for name in FILES:
            paths=[n for n in z.namelist() if n.endswith("/"+name)]
            if len(paths)!=1:raise ValueError("Missing "+name)
            raw=z.read(paths[0])
            if raw[:3]!=b"HSP":raise ValueError("Missing HSP")
            result[name]=inspect(raw[0xc2:])
    out=json.dumps(result,indent=2)+"\n"
    print(out,end="")
    if a.json:a.json.write_text(out)
if __name__=="__main__":main()
