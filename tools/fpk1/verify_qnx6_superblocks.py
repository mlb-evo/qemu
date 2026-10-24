#!/usr/bin/env python3
"""Verify QNX6 superblock signatures and CRC32-BE in expanded FPK1 disks.

QNX6 magic 0x68191122 at 0x2000; checksum CRC32-BE initial 0 over bytes 8..511.
Checks superblock candidates only; no file extraction or write.
"""
import argparse, json, struct, zipfile, zlib, xml.etree.ElementTree as ET
from pathlib import Path
MAGIC=0x68191122
def crc32_be(data):
    crc=0
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc=((crc<<1)^ (0x04c11db7 if (crc&0x80000000) else 0)) & 0xffffffff
    return crc
def expand(z,target):
    for n in z.namelist():
        if not n.endswith("_SignInfo.xml"):continue
        x=ET.fromstring(z.read(n))
        if x.attrib.get("name")!=target:continue
        data=z.read(n.rsplit("/",1)[0]+"/"+target)
        start=int(x.findtext("START-BYTE-FLASHDATA"))
        size=int(x.findtext("COMPRESSED-SIZE"))
        expected=int(x.findtext("UNCOMPRESSED-SIZE"))
        if expected>256*1024*1024:raise ValueError("Excess image size")
        dec=zlib.decompressobj()
        out=dec.decompress(data[start:start+size],expected+1)
        out+=dec.flush()
        if not dec.eof or dec.unused_data or len(out)!=expected:raise ValueError("Bad zlib stream")
        return out
    raise ValueError("Missing "+target)
def candidates(image):
    positions=[]
    magic=struct.pack("<I",MAGIC)
    at=0
    while (at:=image.find(magic,at))>=0:
        positions.append(at)
        at+=4
        if len(positions)>=32:break
    return positions
def inspect(image):
    result=[]
    for at in candidates(image):
        block=image[at:at+512]
        if len(block)<512:continue
        expected=struct.unpack_from("<I",block,4)[0]
        actual=crc32_be(block[8:])
        result.append({
            "offset":hex(at),"is_expected_primary_offset":at==0x2000,
            "magic":hex(struct.unpack_from("<I",block)[0]),
            "checksum_stored_le":f"0x{expected:08x}",
            "checksum_crc32_be":f"0x{actual:08x}",
            "checksum_valid":expected==actual,
            "serial_le":struct.unpack_from("<Q",block,8)[0],
            "superblock_prefix_64":block[:64].hex(),
        })
    return result
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        report={n:inspect(expand(z,n)) for n in ("app.img","stage3.img")}
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
