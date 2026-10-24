#!/usr/bin/env python3
"""Inspect selected non-sensitive QNX6 startup/config text from original FPK1 ZIP.

Read-only. No shadow/passwd/keys and no raw executable extraction.
"""
import argparse,json,zipfile
from pathlib import Path
from probe_qnx6_root import Volume,image_from_signinfo

PATHS={
 "app.img":("/img_ver.txt","/dp/dp_monitor_types.xml"),
 "stage3.img":("/img_ver.txt","/bin/stage3.sh","/bin/startup-common.sh",
               "/bin/inic_emergency_script.sh","/bin/init_core_dump_handling.sh",
               "/etc/mcd.mnt","/etc/build_version.txt","/etc/scripts/extnet.sh")
}
MAX_FILE=16384

def locate(vol,path):
    number=1
    for component in path.strip("/").split("/"):
        node=vol.inode(number)
        if node["mode"]&0xf000!=0x4000:raise ValueError("Not a directory: "+component)
        matches=[entry for entry in vol.directory(node) if entry["name"]==component]
        if len(matches)!=1:raise ValueError("Missing or ambiguous "+path)
        number=matches[0]["inode"]
    return vol.inode(number)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    out={}
    with zipfile.ZipFile(a.archive) as z:
        for name,paths in PATHS.items():
            vol=Volume(image_from_signinfo(z,name))
            entries={}
            for path in paths:
                try:
                    node=locate(vol,path)
                    size=node["size"]
                    if node["mode"]&0xf000!=0x8000:
                        raise ValueError("Not regular file")
                    if size>MAX_FILE:raise ValueError("Text exceeds safety limit")
                    data=vol.read(node,0,size)
                    if b"\x00" in data:raise ValueError("Contains NUL; likely binary")
                    text=data.decode("utf-8")
                    entries[path]={"size":size,"text":text}
                except (ValueError,UnicodeError) as e:
                    entries[path]={"error":str(e)}
            out[name]=entries
    output=json.dumps(out,indent=2,ensure_ascii=False)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)

if __name__=="__main__":main()
