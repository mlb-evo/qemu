#!/usr/bin/env python3
"""Inspect decompressed FPK1 app/stage3 images without writing image files.

Uses exact SignInfo flashdata boundaries; requires valid zlib EOF and
declared output length. Reports hashes, nonzero ranges and common magic
offsets. This is reconnaissance, not filesystem auto-detection.
"""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

TARGETS=("app.img","stage3.img")
MAGICS={
    "qnx_startup":bytes.fromhex("eb7eff00"),
    "qnx_imagefs":b"imagefs",
    "qnx_ifsp_table":b"IFSPTTBL",
    "elf":b"\x7fELF",
    "ext_superblock_magic":bytes.fromhex("53ef"),
    "squashfs_le":b"hsqs",
    "squashfs_be":b"sqsh",
    "ubifs":bytes.fromhex("31181006"),
    "ubi":b"UBI#",
    "android_sparse":bytes.fromhex("3aff26ed"),
    "mbr_footer":bytes.fromhex("55aa"),
}
BLOCK=4096
MAX=256*1024*1024

def unpack(z, member, start, stored, expected):
    if expected > MAX:
        raise ValueError("Declared output too large")
    data=z.read(member)
    compressed=data[start:start+stored]
    if len(compressed)!=stored:
        raise ValueError("Short flashdata")
    decomp=zlib.decompressobj()
    out=decomp.decompress(compressed,expected+1)
    if len(out)>expected:
        raise ValueError("Overlong stream")
    out+=decomp.flush()
    if not decomp.eof or decomp.unused_data or len(out)!=expected:
        raise ValueError("Invalid zlib stream or output size")
    return out

def spans(buf):
    occupied=[]
    for i in range(0,len(buf),BLOCK):
        if any(buf[i:i+BLOCK]):
            if occupied and occupied[-1][1]==i:
                occupied[-1][1]=min(i+BLOCK,len(buf))
            else:
                occupied.append([i,min(i+BLOCK,len(buf))])
    return occupied

def report(buf):
    regions=spans(buf)
    magics={}
    for name,magic in MAGICS.items():
        offsets=[]
        i=0
        while len(offsets)<12:
            at=buf.find(magic,i)
            if at<0:break
            offsets.append(hex(at))
            i=at+1
        magics[name]=offsets
    return {"bytes":len(buf),"sha256":hashlib.sha256(buf).hexdigest(),
            "first_64":buf[:64].hex(),
            "last_64":buf[-64:].hex(),
            "first_nonzero_offset": next((i for i,x in enumerate(buf) if x),None),
            "last_nonzero_end": len(buf.rstrip(b"\x00")),
            "nonzero_4k_ranges":[[hex(x),hex(y)] for x,y in regions[:64]],
            "nonzero_4k_range_count":len(regions),
            "magic_candidates":magics,
            "byte_at_ext_superblock_magic_offset_0x438":buf[0x438:0x43a].hex(),
            "bytes_at_mbr_signature_offset_0x1fe":buf[0x1fe:0x200].hex(),
            "bytes_at_gpt_header_offset_0x200":buf[0x200:0x208].hex()}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    records={}
    with zipfile.ZipFile(a.archive) as z:
        for name in z.namelist():
            if not name.endswith("_SignInfo.xml"):continue
            root=ET.fromstring(z.read(name))
            basename=root.attrib.get("name","")
            if basename not in TARGETS:continue
            member=name.rsplit("/",1)[0]+"/"+basename
            output=unpack(z,member,int(root.findtext("START-BYTE-FLASHDATA")),
                          int(root.findtext("COMPRESSED-SIZE")),
                          int(root.findtext("UNCOMPRESSED-SIZE")))
            records[basename]=report(output)
    if set(records)!=set(TARGETS):
        raise ValueError("Missing SignInfo for requested targets")
    rendered=json.dumps(records,indent=2)+"\n"
    print(rendered,end="")
    if a.json:a.json.write_text(rendered)
if __name__=="__main__":main()
