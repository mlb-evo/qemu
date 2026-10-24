#!/usr/bin/env python3
"""Probe Stage1 QNX startup and imagefs markers without assuming an imagefs catalog.

Read-only: report aligned hex, LE words, exact marker offsets, and startup
signature neighborhoods. All offsets relative to raw HSP member +0xc2.
"""
import argparse,json,struct,zipfile
from pathlib import Path
MARKERS=(b"imagefs",b"#imagefs",b"\xeb\x7e\xff\x00",b"startup-nvidia-tegra3-mm")
def window(data,at):
    a=max(0,at-32);b=min(len(data),at+96)
    return {"at":hex(at),"bytes":data[a:b].hex(" "),
            "start":hex(a),
            "u32_from_marker":[{"at":hex(p),"le":hex(struct.unpack_from("<I",data,p)[0])}
                for p in range(at,min(at+48,len(data)-3),4)],
            "ascii":"".join(chr(x) if 32<=x<127 else "." for x in data[a:b])}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    x=p.parse_args()
    with zipfile.ZipFile(x.archive) as z:
        members=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Stage1 member missing or ambiguous")
        data=z.read(members[0])[0xc2:]
    report={"member":members[0],"coordinate_system":"HSP member offset +0xc2",
            "marker_hits":[]}
    for marker in MARKERS:
        start=0
        while (at:=data.find(marker,start))>=0:
            report["marker_hits"].append({"marker":marker.hex(),"context":window(data,at)})
            start=at+1
            if len(report["marker_hits"])>64:break
    out=json.dumps(report,indent=2)+"\n"
    print(out,end="")
    if x.json:x.json.write_text(out)
if __name__=="__main__":main()
