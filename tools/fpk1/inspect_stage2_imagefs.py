#!/usr/bin/env python3
"""Read-only QNX imagefs catalog inspection of an extracted FPK1 STAGE2.2.

Uses the QNX record layout already implemented by
tools/mhi2/extract_main_ifs.py and tools/mhi2/glforward/ifs_resource.py.
This tool does not attempt to decompress or alter proprietary firmware.
"""
import argparse
import json
import struct
from pathlib import Path

def inspect(data):
    base = 0x890
    if data[base:base+8] != b"imagefs\x04":
        raise ValueError("Expected QNX imagefs v4 at STAGE2.2 +0x890")
    logical_size, data_start, directory = struct.unpack_from("<III", data, base+8)
    if directory < 24 or base+directory >= len(data):
        raise ValueError("Invalid directory offset")
    pos = base + directory
    rows = []
    while pos+2 <= len(data):
        reclen = struct.unpack_from("<H", data, pos)[0]
        if reclen == 0:
            break
        if reclen < 24 or reclen % 4 or pos + reclen > len(data):
            raise ValueError(f"Invalid directory record at {pos:#x}")
        mode = struct.unpack_from("<I", data, pos+8)[0]
        regular = (mode & 0xf000) == 0x8000
        name_at = 32 if regular else 24
        if reclen < name_at+1:
            raise ValueError(f"Truncated record at {pos:#x}")
        rawname = data[pos+name_at:pos+reclen].split(b"\x00",1)[0]
        if not rawname or b"/../" in rawname or rawname.startswith(b"/"):
            raise ValueError(f"Invalid name at {pos:#x}")
        row = {"path":rawname.decode("utf-8","replace"),"record_at":pos,
               "record_size":reclen, "mode":oct(mode)}
        if regular:
            off,size = struct.unpack_from("<II", data, pos+24)
            start,end = base+off,base+off+size
            row.update(offset=off, length=size, physical_start=start,
                       physical_end=end, fully_present=end<=len(data))
        rows.append(row)
        pos += reclen
    regular = [r for r in rows if "length" in r]
    return {"imagefs_base":base, "declared_logical_size":logical_size,
            "data_start":data_start,"directory_offset":directory,
            "region_size":len(data),"catalog_end":pos,
            "total_entries":len(rows),"regular_files":len(regular),
            "fully_present":sum(r["fully_present"] for r in regular),
            "out_of_bounds":sum(not r["fully_present"] for r in regular),
            "max_logical_file_end":max((r["offset"]+r["length"] for r in regular),default=0),
            "entries":rows}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage2_2",type=Path)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    result=inspect(args.stage2_2.read_bytes())
    print(json.dumps({k:v for k,v in result.items() if k!="entries"},indent=2))
    if args.json: args.json.write_text(json.dumps(result,indent=2)+"\n")

if __name__=="__main__":
    main()
