#!/usr/bin/env python3
"""Compare FPK1 firmware images against MHI2 LZOZ / zlib kernel wrappers.

Read-only diagnostic; offset checks are *not* a full format detector.
"""
import argparse
import json
import zipfile
import zlib
from pathlib import Path

NAMES=("stage1_ifs.img","stage1_RECOVERY_ifs.img","stage2_ifs.img")
OFFSETS=(0,0x800,0x808,0x880,0x8a0,0x1000)

def examine(data):
    result={"first_four":data[:4].hex(), "lzoz_header":data[:4]==b"LZOZ",
            "lzoz_anywhere":data.find(b"LZOZ"),"android_header":data[:8]==b"ANDROID!",
            "android_anywhere":data.find(b"ANDROID!"),"zlib_candidates":[]}
    for off in OFFSETS:
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                obj=zlib.decompressobj(wbits)
                output=obj.decompress(data[off:off+131072],1048576)
                if len(output)>100:
                    result["zlib_candidates"].append({"offset":hex(off),"wbits":wbits,
                        "output_length":len(output),"eof":obj.eof,"prefix":output[:16].hex()})
            except zlib.error:
                pass
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("firmware_zip",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.firmware_zip) as z:
        result={}
        for name in NAMES:
            matches=[p for p in z.namelist() if p.endswith(name)]
            if len(matches)!=1: raise ValueError(f"Expected exactly one {name}")
            result[name]=examine(z.read(matches[0])[0xc2:])
    text=json.dumps(result,indent=2)+"\n"
    print(text,end="")
    if args.json:args.json.write_text(text)

if __name__=="__main__": main()
