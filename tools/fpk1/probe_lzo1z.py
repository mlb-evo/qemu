#!/usr/bin/env python3
"""Bounded, read-only LZO1Z offset probes against FPK1 Stage2.1.

Negative results do not identify or exclude a codec.  This is not a
decompressor: it does not guess arbitrary block boundaries.
"""
import argparse
import ctypes
import json
import struct
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mhi2"))
from lzo_library import load_lzo2

OFFSETS = (0x8b1, 0x8b5, 0x8b9, 0x900, 0x1000, 0x2000)
INPUT_LIMIT = 65536
OUTPUT_LIMIT = 262144

def probe(data):
    lzo = load_lzo2()
    call = lzo.lzo1z_decompress_safe
    call.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                     ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
    call.restype = ctypes.c_int
    results = []
    for offset in OFFSETS:
        block = data[offset:offset+INPUT_LIMIT]
        destination = ctypes.create_string_buffer(OUTPUT_LIMIT)
        actual = ctypes.c_size_t(OUTPUT_LIMIT)
        code = call(block, len(block), destination, ctypes.byref(actual), None)
        results.append({"payload_offset":hex(offset),"input_bytes":len(block),
                        "status":code,"output_size_reported":actual.value,
                        "success":code == 0})
    return results

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("archive",type=Path)
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("stage2_ifs.img")]
        if len(names)!=1: raise ValueError("Expected exactly one stage2_ifs.img")
        data=z.read(names[0])[0xc2:]
    if data[0x7f8:0x800] != b"IFSPTTBL":
        raise ValueError("Stage2 table signature mismatch")
    result={"algorithm":"lzo1z_decompress_safe","input_window":INPUT_LIMIT,
            "output_capacity":OUTPUT_LIMIT,"results":probe(data)}
    encoded=json.dumps(result,indent=2)+"\n"
    print(encoded,end="")
    if args.json: args.json.write_text(encoded)

if __name__ == "__main__": main()
