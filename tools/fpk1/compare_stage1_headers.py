#!/usr/bin/env python3
"""Compare QNX startup_header candidates in FPK1 regular/recovery Stage 1.

Read-only, never assumes that a recognizable magic is sufficient for boot.
QNX 6.5 field order: sys/startup.h, 256-byte header.
"""
import argparse
import json
import struct
import zipfile
from pathlib import Path

MAGIC = struct.pack("<I", 0x00ff7eeb)
FIELDS = (
    "signature", "version_flags", "header_machine", "startup_vaddr",
    "paddr_bias", "image_paddr", "ram_paddr", "ram_size",
    "startup_size", "stored_size", "imagefs_paddr", "imagefs_size",
)
NAMES = ("stage1_ifs.img", "stage1_RECOVERY_ifs.img")

def check(raw):
    payload = raw[0xc2:]
    found = []
    pos = 0
    while (pos := payload.find(MAGIC, pos)) != -1:
        if pos + 256 > len(payload):
            break
        values = struct.unpack_from("<12I", payload, pos)
        h = dict(zip(FIELDS, (f"0x{value:08x}" for value in values)))
        image_begin = pos - 8 if pos >= 8 else pos
        available = len(payload) - image_begin
        version = values[1] & 0xffff
        flags1 = (values[1] >> 16) & 0xff
        flags2 = values[1] >> 24
        hsize = values[2] & 0xffff
        machine = values[2] >> 16
        startup_size, stored_size = values[8:10]
        found.append({
            "header_offset": hex(pos),
            "preheader_offset_guess": hex(image_begin),
            "version": hex(version),
            "flags1": hex(flags1),
            "flags2": hex(flags2),
            "header_size": hsize,
            "machine": hex(machine),
            "fields": h,
            "checks": {
                "header_is_256": hsize == 256,
                "startup_fits_available_bytes": startup_size <= available,
                "stored_fits_available_bytes": stored_size <= available,
                "startup_not_larger_than_stored": startup_size <= stored_size,
                "entry_in_potential_loaded_payload": (
                    values[3] >= values[5] and values[3] < values[5] + min(stored_size, available)
                ),
            },
        })
        pos += 4
    return {"raw_size": len(raw), "payload_size": len(payload),
            "magic_candidates": found}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    out = {}
    with zipfile.ZipFile(a.archive) as z:
        names = z.namelist()
        for filename in NAMES:
            matches = [name for name in names if name.endswith("/" + filename)]
            if len(matches) != 1:
                raise ValueError(f"Expected unique {filename}, found {len(matches)}")
            out[filename] = check(z.read(matches[0]))
    data = json.dumps(out, indent=2) + "\n"
    print(data, end="")
    if a.json:
        a.json.write_text(data)

if __name__ == "__main__":
    main()
