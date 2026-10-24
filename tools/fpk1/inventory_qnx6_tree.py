#!/usr/bin/env python3
"""Read-only recursive QNX6 file inventory from signed FPK1 ZIP.

Uses probe_qnx6_root.Volume and prints path, inode, mode and length.
Does not extract proprietary data. Refuses ambiguous long-name entries.
"""
import argparse
import json
import zipfile
from pathlib import Path
from probe_qnx6_root import Volume, image_from_signinfo

def walk(volume, inode_number, path, active, rows, max_entries):
    if len(rows)>=max_entries:
        raise ValueError("Inventory entry limit exceeded")
    inode=volume.inode(inode_number)
    mode=inode["mode"]
    kind="directory" if mode&0xf000==0x4000 else (
        "regular" if mode&0xf000==0x8000 else (
        "symlink" if mode&0xf000==0xa000 else "other"))
    rows.append({"path":path,"inode":inode_number,"type":kind,
                 "mode":oct(mode),"size":inode["size"],
                 "levels":inode["levels"]})
    if kind!="directory":
        return
    if inode_number in active:
        raise ValueError("Directory cycle at "+path)
    active.add(inode_number)
    for item in volume.directory(inode):
        name=item["name"]
        if name in (".",".."):
            continue
        if name=="<long-name-ref>":
            rows.append({"path":path+"/<unresolved-long-name>",
                         "inode":item["inode"],"type":"unresolved"})
            continue
        if "/" in name or name in ("", ".", ".."):
            raise ValueError("Unsafe directory entry name "+repr(name))
        walk(volume,item["inode"],path.rstrip("/")+"/"+name,active,rows,max_entries)
    active.remove(inode_number)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    p.add_argument("--max-entries",type=int,default=10000)
    args=p.parse_args()
    if not 1<=args.max_entries<=100000:
        raise ValueError("Invalid max entries")
    result={}
    with zipfile.ZipFile(args.archive) as z:
        for name in ("app.img","stage3.img"):
            v=Volume(image_from_signinfo(z,name))
            rows=[]
            walk(v,1,"/",set(),rows,args.max_entries)
            result[name]=rows
    output=json.dumps(result,indent=2)+"\n"
    print(output,end="")
    if args.json:
        args.json.write_text(output)

if __name__=="__main__":
    main()
