#!/usr/bin/env python3
"""Inspect MBR partition entries of zlib-expanded FPK1 app/stage3 disk images.

Read-only. Uses SignInfo offsets, validates zlib and sizes, never writes disks.
"""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

TARGETS={"app.img","stage3.img"}
MAX_IMAGE=256*1024*1024
SECTOR=512

def load_image(z, member, xml):
    start=int(xml.findtext("START-BYTE-FLASHDATA"))
    packed=int(xml.findtext("COMPRESSED-SIZE"))
    expected=int(xml.findtext("UNCOMPRESSED-SIZE"))
    if expected>MAX_IMAGE or expected%SECTOR:
        raise ValueError("Invalid expected disk size")
    compressed=z.read(member)[start:start+packed]
    if len(compressed)!=packed: raise ValueError("Incomplete compressed image")
    decoder=zlib.decompressobj()
    image=decoder.decompress(compressed,expected+1)
    if len(image)>expected: raise ValueError("Excess decompressed bytes")
    image+=decoder.flush()
    if not decoder.eof or decoder.unused_data or len(image)!=expected:
        raise ValueError("Bad compressed image length or trailing data")
    return image

def entry(image, i):
    b=image[0x1be+16*i:0x1be+16*(i+1)]
    status=b[0]
    ptype=b[4]
    start,n=struct.unpack_from("<II",b,8)
    end=start+n
    total=len(image)//SECTOR
    present=ptype!=0 or n!=0 or start!=0
    return {
        "slot":i+1, "raw":b.hex(),
        "status":f"0x{status:02x}",
        "partition_type":f"0x{ptype:02x}",
        "start_lba":start, "sector_count":n,
        "end_lba_exclusive":end,
        "start_offset":f"0x{start*SECTOR:x}",
        "present":present,
        "valid_boot_flag":status in (0,0x80),
        "within_image":end<=total and (not present or n>0),
        "partition_first_64":image[start*SECTOR:start*SECTOR+64].hex() if present and n and end<=total else None,
        "partition_boot_signature":image[(start+1)*SECTOR-2:(start+1)*SECTOR].hex() if present and n and end<=total else None,
        "ext_magic_at_partition_plus_0x438":image[start*SECTOR+0x438:start*SECTOR+0x43a].hex() if present and n and end<=total and n*SECTOR>=0x43a else None,
    }

def describe(img):
    entries=[entry(img,i) for i in range(4)]
    return {
        "sha256":hashlib.sha256(img).hexdigest(),
        "size_bytes":len(img),
        "sector_count":len(img)//SECTOR,
        "sector0_first_64":img[:64].hex(),
        "sector0_last_80":img[SECTOR-80:SECTOR].hex(),
        "boot_signature":img[510:512].hex(),
        "partition_table_raw":img[0x1be:0x1fe].hex(),
        "gpt_header_at_lba1":img[512:520].hex(),
        "entries":entries,
        "all_nonempty_entries_plausible":all(e["valid_boot_flag"] and e["within_image"] for e in entries if e["present"]),
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    result={}
    with zipfile.ZipFile(a.archive) as z:
        for path in z.namelist():
            if not path.endswith("_SignInfo.xml"):continue
            xml=ET.fromstring(z.read(path))
            basename=xml.attrib.get("name")
            if basename not in TARGETS:continue
            member=path.rsplit("/",1)[0]+"/"+basename
            result[basename]=describe(load_image(z,member,xml))
    if set(result)!=TARGETS: raise ValueError("Missing target images")
    output=json.dumps(result,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)

if __name__=="__main__":main()
