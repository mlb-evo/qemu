#!/usr/bin/env python3
"""Classify nonzero gaps between reconstructed Stage1 ELF extents.

Only JSON metadata; no payloads written to disk.
"""
import argparse,collections,json,math,re,struct,zipfile
from pathlib import Path
from map_stage1_decoded_regions import summarize
from validate_stage1_unseeded_lzf import decode

def entropy(chunk):
    if not chunk:return 0.0
    n=len(chunk);counts=collections.Counter(chunk)
    return round(-sum((x/n)*math.log2(x/n) for x in counts.values()),3)

def probe(data,begin,end):
    buf=data[begin:end]
    strings=[]
    for m in re.finditer(rb"[\x20-\x7e]{8,}",buf):
        if len(strings)>=20:break
        strings.append({"offset":hex(begin+m.start()),"text":m.group()[:120].decode("ascii")})
    signatures={}
    for key,needle in (("ELF",b"\x7fELF"),("QNX_imagefs",b"imagefs"),("gzip",b"\x1f\x8b\x08"),
                       ("zlib_789c",b"\x78\x9c"),("shebang",b"#!"),("qnx_path",b"/usr/")):
        signatures[key]=buf.count(needle)
    return {"start":hex(begin),"end":hex(end),"bytes":len(buf),
            "nonzero":sum(v!=0 for v in buf),"entropy":entropy(buf),
            "strings":strings,"signatures":signatures}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous primary Stage1")
        raw=z.read(names[0])
    decoded,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    areas=[]
    for item in summarize(decoded):
        end=item["next_elf"]
        begin=item["usable_extent_end"]
        if not end or not begin or item["between_nonzero"]<100:
            continue
        areas.append({"after_elf":item["elf"],"section_issue":item["section_issue"],
                      **probe(decoded,int(begin,16),int(end,16))})
    areas.sort(key=lambda x:x["nonzero"],reverse=True)
    result={"regions":areas,"note":"Gap boundaries are ELF-derived lower bounds, not verified filesystem file extents."}
    output=json.dumps(result,indent=2)+"\n";print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
