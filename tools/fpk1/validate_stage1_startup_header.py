#!/usr/bin/env python3
"""Validate FPK1 stage1 candidate against the documented QNX 6.5 startup_header.

Read-only; deliberately rejects incoherent header sizes and never infers a boot PC.
"""
import argparse,json,struct,zipfile
from pathlib import Path
FIELDS=("signature","version_flags","header_machine","startup_vaddr","paddr_bias","image_paddr","ram_paddr","ram_size","startup_size","stored_size","imagefs_paddr","imagefs_size")
def inspect(blob):
    base=0x808
    words=struct.unpack_from("<12I",blob,base)
    v=dict(zip(FIELDS,words))
    header_size=words[2]&0xffff
    machine=words[2]>>16
    return {"candidate_at":hex(base),"fields":{k:hex(x) for k,x in v.items()},
            "version":hex(words[1]&0xffff),"flags1":(words[1]>>16)&255,"flags2":words[1]>>24,
            "header_size":header_size,"machine":hex(machine),
            "stored_size_fits_payload":words[9]<=len(blob)-base,
            "startup_size_fits_stored":words[8]<=words[9],
            "startup_size_fits_payload":words[8]<=len(blob)-base,
            "consistent_boot_header":header_size==256 and words[8]<=words[9]<=len(blob)-base,
            "warning":"Magic/version/CPU type are plausible but size fields contradict image; no QNX IPL handoff established."}
def main():
    p=argparse.ArgumentParser();p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        n=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(n)!=1:raise ValueError("Expected unique stage1_ifs.img")
        data=z.read(n[0])[0xc2:]
    result=inspect(data)
    s=json.dumps(result,indent=2)+"\n";print(s,end="")
    if a.json:a.json.write_text(s)
if __name__=="__main__":main()
