#!/usr/bin/env python3
"""Validate Stage2.2 imagefs extents against an extracted region; stdlib only.

Input must be the *Stage2.2 region* (not the original HSP update image).
No binary firmware is committed to this repository.
"""
import argparse
import json
import struct
from pathlib import Path

def inspect(data):
    base = data.find(b"imagefs")
    if base < 0:
        raise ValueError("imagefs marker not found")
    # Previously identified Stage2.2 imagefs header; avoid accepting a
    # coincidental occurrence elsewhere without its expected relative offset.
    if base != 0x890:
        raise ValueError(f"unexpected imagefs marker offset: {base:#x}")
    pos = 0x908
    records = []
    while pos + 36 <= len(data):
        size, flags, mode, uid, gid, mtime, offset, length = struct.unpack_from("<8I", data, pos)
        if size < 36 or size > 2048 or size % 4 or pos + size > len(data):
            break
        name_raw = data[pos+32:pos+size].split(b"\x00", 1)[0]
        if not name_raw or any(c < 32 or c > 126 for c in name_raw):
            break
        name = name_raw.decode("ascii")
        absolute_start = base + offset
        absolute_end = absolute_start + length
        records.append(dict(path=name, record_at=pos, offset=offset, length=length,
                            absolute_start=absolute_start, absolute_end=absolute_end,
                            in_bounds=(absolute_end <= len(data))))
        pos += size
    return dict(imagefs_base=base, region_size=len(data), table_end=pos,
                record_count=len(records),
                fully_in_bounds=sum(x["in_bounds"] for x in records),
                beyond_region=sum(not x["in_bounds"] for x in records),
                max_logical_end=max((x["offset"]+x["length"] for x in records), default=0),
                records=records)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage2_2", type=Path)
    p.add_argument("--json", type=Path)
    args=p.parse_args()
    result=inspect(args.stage2_2.read_bytes())
    summary={k:v for k,v in result.items() if k!="records"}
    print(json.dumps(summary, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2)+"\n")

if __name__ == "__main__":
    main()
