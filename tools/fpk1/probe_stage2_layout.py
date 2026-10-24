#!/usr/bin/env python3
"""Cross-check Stage2 partition table against embedded imagefs size metadata."""
import argparse
import json
import struct
import zipfile
from pathlib import Path

def u32(data, at):
    return struct.unpack_from("<I", data, at)[0]

def inspect(data):
    if data[0x7f8:0x800] != b"IFSPTTBL":
        raise ValueError("Missing IFSPTTBL at 0x7f8")
    first, second = 0x818, 0x844
    if data[first:first+8] != b"STAGE2.1" or data[second:second+8] != b"STAGE2.2":
        raise ValueError("Unexpected partition names")
    stored = u32(data, first + 8 + 4*4)
    logical = u32(data, first + 8 + 5*4)
    tag = data.find(b"#imagefs", 0x880, stored)
    if tag < 0:
        raise ValueError("Missing Stage2.1 imagefs tag")
    # One byte follows '#imagefs' before the LE logical-size value.
    embedded = u32(data, tag + len(b"#imagefs") + 1)
    region_start = u32(data, second + 8 + 3*4)
    region_size = u32(data, second + 8 + 4*4)
    marker = data.find(b"imagefs", region_start, region_start + region_size)
    return {
        "stage21_stored_size_field": hex(stored),
        "stage21_logical_size_field": hex(logical),
        "stage21_imagefs_tag_at": hex(tag),
        "stage21_embedded_size_field": hex(embedded),
        "stage21_size_fields_match": logical == embedded,
        "stage22_region_start": hex(region_start),
        "stage22_region_size": hex(region_size),
        "stage22_imagefs_text_at": hex(marker),
        "stage22_imagefs_relative_offset": hex(marker-region_start),
        "stage22_first_32_bytes": data[region_start:region_start+32].hex(" "),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        name = next(n for n in z.namelist() if n.endswith("/stage2_ifs.img"))
        payload = z.read(name)[0xc2:]
    result = inspect(payload)
    print(json.dumps(result, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n")

if __name__ == "__main__":
    main()
