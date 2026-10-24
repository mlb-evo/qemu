#!/usr/bin/env python3
"""Probe exact SignInfo FLASHDATA for zlib streams with bounded output.

No implicit 0xc2 offset: use START-BYTE-FLASHDATA and COMPRESSED-SIZE.
Does not modify source archive or store unpacked proprietary data by default.
"""
import argparse, json, zipfile, zlib
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_OUTPUT=256*1024*1024

def inspect(data, expected):
    if expected>MAX_OUTPUT:
        return {"status":"size_limit","expected":expected}
    obj=zlib.decompressobj()
    try:
        out=obj.decompress(data,expected+1)
        if len(out)>expected:
            return {"status":"output_exceeds_signinfo"}
        out+=obj.flush(expected+1-len(out))
        return {"status":"ok" if obj.eof and len(out)==expected and not obj.unused_data else "mismatch",
                "output_bytes":len(out),"eof":obj.eof,
                "unused_bytes":len(obj.unused_data),"prefix":out[:16].hex()}
    except zlib.error as e:
        return {"status":"not_zlib","error":str(e)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    result=[]
    with zipfile.ZipFile(args.archive) as z:
        names=set(z.namelist())
        for path in sorted(n for n in names if n.endswith("_SignInfo.xml")):
            root=ET.fromstring(z.read(path))
            member=path.rsplit("/",1)[0]+"/"+root.attrib["name"]
            if member not in names:continue
            start=int(root.findtext("START-BYTE-FLASHDATA"))
            stored=int(root.findtext("COMPRESSED-SIZE"))
            expected=int(root.findtext("UNCOMPRESSED-SIZE"))
            if expected==stored:continue
            raw=z.read(member)
            data=raw[start:start+stored]
            if len(data)!=stored:raise ValueError("Truncated member: "+member)
            result.append({"member":member,"stored":stored,"expected":expected,
                           "prefix":data[:8].hex(),"zlib":inspect(data,expected)})
    text=json.dumps(result,indent=2)+"\n"
    print(text,end="")
    if args.json:args.json.write_text(text)

if __name__=="__main__":main()
