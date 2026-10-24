#!/usr/bin/env python3
"""Inspect FPK1 Quickboot primary/recovery wrappers without modifying firmware.

MHI2's prepare.py assumes [stage2_length:u32][stage1_length:u32][bytes...].
This tool checks that assumption rather than applying it to FPK1 blindly.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

NAMES=("qb_primary.img","qb_recovery.img")
HSP_PAYLOAD_OFFSET=0xc2

def inspect(raw):
    if raw[:3] != b"HSP":
        raise ValueError("Missing HSP marker")
    declared=struct.unpack_from("<I", raw, 0x14)[0]
    payload=raw[HSP_PAYLOAD_OFFSET:]
    a,b=struct.unpack_from("<II",payload,0)
    return {
        "file_size":len(raw),
        "declared_payload_size":declared,
        "payload_offset":HSP_PAYLOAD_OFFSET,
        "payload_size":len(payload),
        "declared_matches_payload":declared==len(payload),
        "payload_sha256":hashlib.sha256(payload).hexdigest(),
        "payload_first_32_hex":payload[:32].hex(" "),
        "mhi2_first_length":a,
        "mhi2_second_length":b,
        "mhi2_length_fields_consistent":a+b+8==len(payload),
    },payload

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("firmware_zip",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.firmware_zip) as z:
        reports={}
        payloads=[]
        for name in NAMES:
            paths=[p for p in z.namelist() if p.endswith("/"+name)]
            if len(paths)!=1: raise ValueError(f"Expected exactly one {name}")
            report,payload=inspect(z.read(paths[0]))
            reports[name]=report
            payloads.append(payload)
    reports["comparison"]={
        "payloads_identical":payloads[0]==payloads[1],
        "differing_payload_bytes":sum(x!=y for x,y in zip(*payloads)) + abs(len(payloads[0])-len(payloads[1])),
    }
    text=json.dumps(reports,indent=2)+"\n"
    print(text,end="")
    if args.json:args.json.write_text(text)

if __name__=="__main__":main()
