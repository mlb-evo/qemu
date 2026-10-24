#!/usr/bin/env python3
"""Inspect FPK1 Stage2 boundaries and compare stored/logical IFS extents.

Read-only. Input: original update ZIP. No claim about compression codec.
"""
import argparse
import collections
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

def entropy(data):
    counts=collections.Counter(data)
    n=len(data)
    return -sum((v/n)*math.log2(v/n) for v in counts.values())

def inspect(payload):
    if payload[0x7f8:0x800] != b"IFSPTTBL":
        raise ValueError("Unexpected Stage2 table signature")
    if payload[0x818:0x820] != b"STAGE2.1" or payload[0x844:0x84c] != b"STAGE2.2":
        raise ValueError("Unexpected partition names")
    first_stored, first_logical=struct.unpack_from("<II", payload,0x830)
    second_start, second_stored=struct.unpack_from("<II",payload,0x858)
    first_marker=payload.find(b"#imagefs\x04",0x880,0x1000)
    second_marker=payload.find(b"imagefs\x04",second_start,second_start+0x2000)
    if first_marker != 0x8a0 or second_marker != second_start+0x890:
        raise ValueError("Unexpected imagefs marker locations")
    second_logical=struct.unpack_from("<I",payload,second_marker+8)[0]
    if struct.unpack_from("<I",payload,first_marker+9)[0] != first_logical:
        raise ValueError("Stage2.1 logical size mismatch")
    windows=[
        ("stage21_metadata",0x880,0x2000),
        ("stage21_middle",0x100000,0x110000),
        ("stage21_tail",second_start-0x1000,second_start),
        ("stage22_head",second_start,second_start+0x1000),
        ("stage22_middle",0xa00000,0xa10000),
        ("stage22_tail",second_start+second_stored-0x1000,second_start+second_stored)
    ]
    samples=[]
    for name,begin,end in windows:
        buf=payload[begin:end]
        if len(buf)!=end-begin: raise ValueError("Truncated sample")
        samples.append(dict(name=name,start=hex(begin),end=hex(end),
                            entropy_bits_per_byte=round(entropy(buf),4),
                            sha256=hashlib.sha256(buf).hexdigest(),
                            most_common=collections.Counter(buf).most_common(4)))
    return dict(stage21_stored_field=first_stored,stage21_logical_field=first_logical,
                stage22_offset=second_start,stage22_stored_field=second_stored,
                stage22_logical_imagefs=second_logical,
                stage21_marker=hex(first_marker),stage22_marker=hex(second_marker),
                stage22_marker_relative=hex(second_marker-second_start),
                samples=samples)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("stage2_ifs.img")]
        if len(names)!=1: raise ValueError("Expected exactly one stage2_ifs.img")
        raw=z.read(names[0])
    result=inspect(raw[0xc2:])
    encoded=json.dumps(result,indent=2)+"\n"
    print(encoded,end="")
    if args.json: args.json.write_text(encoded)
if __name__ == "__main__":
    main()
