#!/usr/bin/env python3
"""Compare primary and recovery Stage1 first 0x800 bytes (metadata only).

Does not export firmware. Labels numeric values as hypotheses only.
"""
import argparse, json, struct, zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path);p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        paths=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(paths)!=1:raise ValueError("Cannot uniquely find primary Stage1")
        raw=z.read(paths[0]); data=raw[0xc2:]
    words=[]
    for off in range(0,0x800,4):
        value=struct.unpack_from("<I",data,off)[0]
        if value:
            words.append({"at":hex(off),"value":hex(value),
                          "equals_inner_length":value==len(data),
                          "in_inner_bounds":value<len(data)})
    strings=[]
    import re
    for m in re.finditer(rb"[\x20-\x7e]{8,}",data[:0x800]):
        strings.append({"at":hex(m.start()),"text":m.group().decode("ascii")})
    result={"inner_size":hex(len(data)),"hsp_size_words":raw[0x10:0x18].hex(),
            "inner_first_0x800_nonzero_u32":words[:150],
            "early_strings":strings[:25],
            "inner_0x800_first_16":data[0x800:0x810].hex(),
            "warning":"No field semantics or IFS codec block start inferred from values alone."}
    payload=json.dumps(result,indent=2)+"\n"
    print(payload,end="")
    if a.json:a.json.write_text(payload)
if __name__=="__main__":main()
