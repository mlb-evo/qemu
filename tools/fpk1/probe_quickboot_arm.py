#!/usr/bin/env python3
"""Read-only ARM-state prologue / literal-pool probe for FPK1 Quickboot.

Reports file-relative offsets, *not* inferred runtime virtual addresses.
No firmware images are stored in the repository.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]

def sign_extend_26(n):
    return n - (1 << 26) if n & (1 << 25) else n

def inspect(payload):
    instructions = []
    for at in range(0, min(0x78, len(payload)), 4):
        word = u32(payload, at)
        row = {"offset": hex(at), "word": f"{word:08x}"}
        if (word & 0x0e000000) == 0x0a000000:
            displacement = sign_extend_26((word & 0x00ffffff) << 2)
            row["branch_target_file_relative"] = hex(at + 8 + displacement)
            row["branch_kind"] = "BL" if (word & 0x01000000) else "B"
        if (word & 0x0f7f0000) == 0x051f0000:
            delta = word & 0xfff
            target = at + 8 + (delta if word & (1 << 23) else -delta)
            row["ldr_literal_file_offset"] = hex(target)
            if target >= 0 and target + 4 <= len(payload):
                row["ldr_literal_value"] = f"0x{u32(payload,target):08x}"
        instructions.append(row)
    return {
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "first_32_bytes": payload[:32].hex(" "),
        "starts_with_arm_function_prologue": payload[:4] == bytes.fromhex("30402de9"),
        "instructions": instructions,
        "limitations": "ARM-state best-effort instruction patterns; file-relative branches, no load address, no proof of boot entry."
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("archive",type=Path)
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    result={}
    with zipfile.ZipFile(args.archive) as z:
        for name in ("qb_primary.img","qb_recovery.img"):
            candidates=[n for n in z.namelist() if n.endswith("/"+name)]
            if len(candidates)!=1:
                raise ValueError(f"Expected exactly one {name}")
            full=z.read(candidates[0])
            if full[:3]!=b"HSP":raise ValueError("Expected HSP header")
            result[name]=inspect(full[0xc2:])
    result["identical_payloads"]=result["qb_primary.img"]["sha256"]==result["qb_recovery.img"]["sha256"]
    output=json.dumps(result,indent=2)+"\n"
    print(output,end="")
    if args.json:args.json.write_text(output)

if __name__=="__main__":
    main()
