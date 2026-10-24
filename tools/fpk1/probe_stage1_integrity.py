#!/usr/bin/env python3
"""Inspect FPK1 Stage1 container control fields and test CRC32 hypotheses.

Read-only; CRC matches are correlations, not format proof.
"""
import argparse
import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path

FILES=("stage1_ifs.img","stage1_RECOVERY_ifs.img")
def analyze(raw):
    if raw[:3] != b"HSP":
        raise ValueError("Expected HSP wrapper")
    d=raw[0xc2:]
    declared=struct.unpack_from("<I",d,0)[0]
    target=struct.unpack_from("<I",d,0x25c)[0]
    regions={
        "payload_from_0x800":d[0x800:],
        "payload_0x800_to_declared":d[0x800:declared],
        "payload_0x800_to_eof_minus_8":d[0x800:-8],
        "whole_payload":d,
        "header_0_to_0x7f4":d[:0x7f4],
        "header_0x4_to_0x7f4":d[4:0x7f4],
    }
    checks=[]
    for name,buf in regions.items():
        crc=zlib.crc32(buf)&0xffffffff
        adler=zlib.adler32(buf)&0xffffffff
        checks.append({"region":name,"length":len(buf),
                       "crc32":f"0x{crc:08x}","adler32":f"0x{adler:08x}",
                       "matches_header_u32":crc==target or adler==target})
    return {
        "payload_size":len(d),"size_field_0x0":declared,
        "size_field_residual":len(d)-declared,
        "mode_field_0x258":struct.unpack_from("<I",d,0x258)[0],
        "value_field_0x25c":f"0x{target:08x}",
        "last_12_header_bytes_0x7f4":d[0x7f4:0x800].hex(),
        "last_8_file_bytes":d[-8:].hex(),
        "trailing_zero_run_before_footer":
            len(d[:-8])-len(d[:-8].rstrip(b"\x00")),
        "sha256":hashlib.sha256(d).hexdigest(),
        "checksums":checks,
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    report={}
    with zipfile.ZipFile(a.archive) as z:
        for n in FILES:
            matches=[s for s in z.namelist() if s.endswith("/"+n)]
            if len(matches)!=1:raise ValueError(f"Expected one {n}")
            report[n]=analyze(z.read(matches[0]))
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
