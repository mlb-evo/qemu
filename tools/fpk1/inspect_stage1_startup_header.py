#!/usr/bin/env python3
"""Inspect QNX startup_header fields of the original Stage1 IFS.

This is intentionally a header probe, not a decompressor. Uses offsets from
QNX sys/startup.h and reports candidate physical bounds for validation.
"""
import argparse, json, struct, zipfile
from pathlib import Path

MAGIC=0x00ff7eeb
FLAG_COMPRESSION={0:"none",4:"zlib",8:"lzo",12:"ucl"}

def inspect(data,at):
    u16=lambda pos:struct.unpack_from("<H",data,at+pos)[0]
    u32=lambda pos:struct.unpack_from("<I",data,at+pos)[0]
    flags1=data[at+6]
    fields={
        "signature":hex(u32(0)),
        "version_u16":u16(4),
        "version_low_byte":data[at+4],
        "version_high_byte":data[at+5],
        "flags1":hex(flags1),
        "flags2":hex(data[at+7]),
        "header_size":u16(8),
        "machine":u16(10),
        "startup_vaddr":hex(u32(12)),
        "paddr_bias":hex(u32(16)),
        "image_paddr":hex(u32(20)),
        "ram_paddr":hex(u32(24)),
        "ram_size":u32(28),
        "startup_size":u32(32),
        "stored_size":u32(36),
        "imagefs_paddr":hex(u32(40)),
        "imagefs_size":u32(44),
        "preboot_size":u16(48),
        "compression_kind":FLAG_COMPRESSION.get(flags1&0x1c,"unknown"),
        "compression_bits":hex(flags1&0x1c),
        "header_first_64":data[at:at+64].hex(),
        "standard_header_version_valid":u16(4)==1,
    }
    return fields

def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Stage1 not uniquely found")
        data=z.read(names[0])[0xc2:]
    hits=[]
    magic=struct.pack("<I",MAGIC)
    pos=0
    while (pos:=data.find(magic,pos))>=0:
        if pos+256<=len(data):
            hdr=inspect(data,pos)
            version_ok=hdr["standard_header_version_valid"]
            sizes_ok=(256<=hdr["startup_size"]<=hdr["stored_size"]<=len(data))
            address_ok=(hdr["ram_size"]>=hdr["startup_size"] and hdr["imagefs_size"]<=hdr["ram_size"])
            hdr.update(offset=hex(pos),
                       standard_size_fields_plausible=sizes_ok,
                       standard_address_fields_plausible=address_ok,
                       standard_header_interpretation_valid=(version_ok and sizes_ok and address_ok),
                       note="Raw fields only; invalid standard layout must not drive boot/load bounds" if not(version_ok and sizes_ok and address_ok) else "Standard layout plausibly valid",
                       candidate_image_base=hex(pos-hdr["preboot_size"]) if version_ok and sizes_ok and pos>=hdr["preboot_size"] else None,
                       stored_extent_in_bounds=(version_ok and sizes_ok and pos>=hdr["preboot_size"] and pos-hdr["preboot_size"]+hdr["stored_size"]<=len(data)))
            hits.append(hdr)
        pos+=4
    result={"member":names[0],"coordinates":"HSP raw member + 0xc2","headers":hits}
    txt=json.dumps(result,indent=2)+"\n"
    print(txt,end="")
    if a.json:a.json.write_text(txt)

if __name__=="__main__":main()
