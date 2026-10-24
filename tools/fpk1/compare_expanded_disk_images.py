#!/usr/bin/env python3
"""Compare expanded FPK1 app/stage3 images by sectors and boot-sector metadata.

These images have an x86-like boot sector, but invalid standard MBR entries.
The tool is read-only and never exports proprietary image bytes.
"""
import argparse, hashlib, json, struct, xml.etree.ElementTree as ET, zipfile, zlib
from pathlib import Path

def load(z, target):
    for path in z.namelist():
        if not path.endswith("_SignInfo.xml"): continue
        root=ET.fromstring(z.read(path))
        if root.attrib.get("name")!=target: continue
        name=path.rsplit("/",1)[0]+"/"+target
        raw=z.read(name)
        offset=int(root.findtext("START-BYTE-FLASHDATA"))
        length=int(root.findtext("COMPRESSED-SIZE"))
        expected=int(root.findtext("UNCOMPRESSED-SIZE"))
        if expected>256*1024*1024:raise ValueError("Too large")
        d=zlib.decompressobj()
        out=d.decompress(raw[offset:offset+length],expected+1)
        out+=d.flush()
        if not d.eof or d.unused_data or len(out)!=expected:
            raise ValueError("Invalid zlib data")
        return out
    raise ValueError("No SignInfo: "+target)

def summarize(a,b):
    sector=512
    same=0
    first=None
    diffs=[]
    for i in range(len(a)//sector):
        start=i*sector
        if a[start:start+sector]==b[start:start+sector]:same+=1
        else:
            if first is None:first=i
            if len(diffs)<32: diffs.append(i)
    return {"sectors":len(a)//sector,"same_sectors":same,
            "different_sectors":len(a)//sector-same,
            "first_different_sector":first,
            "first_32_different_sectors":diffs,
            "first_sector_identical":a[:512]==b[:512],
            "first_4096_identical":a[:4096]==b[:4096]}
def boot(b):
    return {"first_512_sha256":hashlib.sha256(b[:512]).hexdigest(),
            "jump_instruction":b[:3].hex(),
            "oem_id_ascii":b[3:11].decode("ascii","replace"),
            "bpb_bytes_per_sector":struct.unpack_from("<H",b,11)[0],
            "bpb_sectors_per_cluster":b[13],
            "bpb_reserved_sectors":struct.unpack_from("<H",b,14)[0],
            "bpb_fat_count":b[16],
            "bpb_root_entries":struct.unpack_from("<H",b,17)[0],
            "bpb_total_sectors_16":struct.unpack_from("<H",b,19)[0],
            "bpb_sectors_per_fat_16":struct.unpack_from("<H",b,22)[0],
            "bpb_total_sectors_32":struct.unpack_from("<I",b,32)[0],
            "bpb_plausible":(struct.unpack_from("<H",b,11)[0] in (512,1024,2048,4096)
                    and b[13] in (1,2,4,8,16,32,64,128)
                    and b[16] in (1,2)),
            "signature_55aa":b[510:512].hex()}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        app=load(z,"app.img")
        stage3=load(z,"stage3.img")
    if len(app)!=len(stage3):raise ValueError("Different disk sizes")
    result={"app_boot":boot(app),"stage3_boot":boot(stage3),
            "comparison":summarize(app,stage3)}
    output=json.dumps(result,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
