#!/usr/bin/env python3
"""Compare FPK1 Stage1 primary/recovery payload headers and data regions.

All offsets are within the candidate HSP-stripped payload (0xC2 bytes).
No decryption, binary patching, or inferred entry point.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

NAMES=("stage1_ifs.img","stage1_RECOVERY_ifs.img")

def entropy(b):
    if not b:
        return None
    counts=Counter(b)
    return round(-sum((n/len(b))*math.log2(n/len(b))
                      for n in counts.values()), 4)

def scan(z, path):
    raw=z.read(path)
    if raw[:3]!=b"HSP":
        raise ValueError("Expected HSP envelope")
    data=raw[0xc2:]
    indicated_size=struct.unpack_from("<I",data,0)[0]
    windows=[]
    for start in (0,0x40,0x100,0x400,0x7c0,0x800,0x900,0x1000,0x2000):
        region=data[start:start+0x100]
        windows.append({"offset":hex(start),"entropy":entropy(region),
                        "sha256":hashlib.sha256(region).hexdigest(),
                        "first_16":region[:16].hex(" ")})
    return data, {
        "archive_member":path,"payload_length":len(data),
        "size_field_at_0":indicated_size,
        "size_field_vs_payload_difference":len(data)-indicated_size,
        "u32_header_le":[f"0x{x:08x}" for x in struct.unpack_from("<16I",data,0)],
        "qnx_signature_offset":data.find(bytes.fromhex("eb7eff00")),
        "imagefs_offset":data.find(b"imagefs"),
        "windows":windows,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        parsed={}
        for filename in NAMES:
            paths=[s for s in z.namelist() if s.endswith("/"+filename)]
            if len(paths)!=1:raise ValueError(f"Expected unique {filename}")
            parsed[filename]=scan(z,paths[0])
    primary, recovery=(parsed[name][0] for name in NAMES)
    first_difference=next((i for i,(x,y) in enumerate(zip(primary,recovery))
                           if x!=y),min(len(primary),len(recovery)))
    # Ignore the first 4 bytes (different size fields) when checking a common header.
    identical_after_size=4
    while (identical_after_size < min(len(primary),len(recovery)) and
           primary[identical_after_size]==recovery[identical_after_size]):
        identical_after_size+=1
    output={name:parsed[name][1] for name in NAMES}
    output["comparison"]={
        "first_differing_offset":hex(first_difference),
        "identical_header_run_after_size_field_end":hex(identical_after_size),
        "first_difference_after_size_field":hex(identical_after_size),
        "prefix_0x800_equal_excluding_length":
            primary[4:0x800]==recovery[4:0x800],
        "bytes_different_0x40_to_0x800":
            sum(x!=y for x,y in zip(primary[0x40:0x800],recovery[0x40:0x800])),
        "note":"Offset 0 size field is a candidate length only; not validated."
    }
    rendered=json.dumps(output,indent=2)+"\n"
    print(rendered,end="")
    if a.json:a.json.write_text(rendered)

if __name__=="__main__":main()
