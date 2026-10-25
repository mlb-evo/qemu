#!/usr/bin/env python3
"""Group Stage1 QNX build-information fields without assuming NUL delimiters.

Matches the proven loose field scanner. NAME-to-description assignments are
heuristic based on coordinates, never confirmed filesystem catalog entries.
"""
import argparse,bisect,json,re,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

PAT=re.compile(rb"(NAME|DESCRIPTION|DATE|STATE|HOST|USER)=([\x20-\x7e]{1,200})")

def collect(buf):
    fields=[]
    for m in PAT.finditer(buf):
        fields.append({"at":m.start(),"key":m.group(1).decode("ascii"),
                       "value":m.group(2).decode("ascii")})
    records=[]
    current=None
    orphan=[]
    for field in fields:
        if field["key"]=="NAME":
            if current is not None:records.append(current)
            current={"start":hex(field["at"]),"fields":{"NAME":field["value"]},
                     "field_offsets":{"NAME":hex(field["at"])},
                     "end":hex(field["at"]+len(field["value"])+5)}
        elif current is not None:
            # A large separation may be another object; do not merge blindly.
            if field["at"]-int(current["end"],16)>4096:
                records.append(current)
                current=None
                orphan.append(field)
                continue
            current["fields"][field["key"]]=field["value"]
            current["field_offsets"][field["key"]]=hex(field["at"])
            current["end"]=hex(field["at"]+len(field["key"])+1+len(field["value"]))
        else:orphan.append(field)
    if current is not None:records.append(current)
    return records

def associate(buf):
    records=collect(buf)
    elfs=sorted(e["at"] for e in scan_elf(buf) if e["strict_elf_valid"])
    items=[]
    for record in records:
        pos=int(record["start"],16)
        i=bisect.bisect_right(elfs,pos)-1
        prev=elfs[i] if i>=0 else None
        nxt=elfs[i+1] if i+1<len(elfs) else None
        items.append({**record,"preceding_elf":hex(prev) if prev is not None else None,
                      "distance_from_elf":pos-prev if prev is not None else None,
                      "next_elf":hex(nxt) if nxt is not None else None})
    return {"strict_elf_count":len(elfs),"records":items,"record_count":len(items),
            "names_by_preceding_elf":{hex(at):[x["fields"]["NAME"] for x in items
            if x["preceding_elf"]==hex(at)] for at in elfs},
            "warning":"NAME boundaries come from field occurrences, not proven binary metadata framing. Field ownership is heuristic."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    buf,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    output=json.dumps({"decoded_length":len(buf),"encoded_stop":hex(stop),**associate(buf)},indent=2)+"\n"
    print(output,end="")
    if args.json:args.json.write_text(output)
if __name__=="__main__":main()
