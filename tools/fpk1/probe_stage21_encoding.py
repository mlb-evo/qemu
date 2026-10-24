#!/usr/bin/env python3
"""Conservative Stage2.1 content probe. No decompression claims."""
import argparse
import json
import struct
import zipfile
from pathlib import Path

MAGICS = {
    "gzip": bytes.fromhex("1f8b08"),
    "xz": bytes.fromhex("fd377a585a00"),
    "bzip2": b"BZh",
    "lz4_frame": bytes.fromhex("04224d18"),
    "zstd_frame": bytes.fromhex("28b52ffd"),
    "lzo_container": bytes.fromhex("894c5a4f"),
}

def inspect(payload):
    if payload[0x7f8:0x800] != b"IFSPTTBL" or payload[0x818:0x820] != b"STAGE2.1":
        raise ValueError("Unexpected Stage2 partition table")
    stored, logical = struct.unpack_from("<II", payload, 0x830)
    tag = payload.find(b"#imagefs", 0x880, 0x1000)
    if tag != 0x8a0:
        raise ValueError(f"Unexpected imagefs marker: {tag:#x}")
    embedded = struct.unpack_from("<I", payload, tag+9)[0]
    if stored > len(payload):
        raise ValueError("Invalid stored extent")
    body = payload[0x880:stored]
    paths = [p for p in (b"usr/lib/terminfo", b"/mnt", b"usblauncher", b"etc/mcd.")
             if p in body[:0x2000]]
    return {
        "stored_length": stored,
        "logical_length": logical,
        "embedded_length": embedded,
        "matched": logical == embedded,
        "logical_to_stored_ratio": round(logical/stored, 4),
        "tag_offset": tag,
        "visible_early_paths": [p.decode("ascii") for p in paths],
        "common_framed_magic_counts": {k: body.count(v) for k,v in MAGICS.items()},
        "note": "Absence of framed magic does not rule out raw or proprietary compression.",
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("firmware_zip", type=Path)
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    with zipfile.ZipFile(args.firmware_zip) as z:
        name = next(n for n in z.namelist() if n.endswith("/stage2_ifs.img"))
        payload = z.read(name)[0xc2:]
    result = inspect(payload)
    print(json.dumps(result, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2)+"\n")

if __name__ == "__main__":
    main()
