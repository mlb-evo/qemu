#!/usr/bin/env python3
"""Find bounded QNX build records and rank association to recovered Stage1 ELF.

Each record starts at a NAME= string (possibly preceded by a build-info prefix), contains adjacent
NUL-terminated key/value strings, and ends at next NAME or a large separation.
Metadata ownership is inferred and never equated with an imagefs catalog.
"""
import argparse,bisect,json,re,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode,scan_elf

FIELDS=(b"NAME",b"DESCRIPTION",b"DATE",b"STATE",b"HOST",b"USER")
KEYS=set(FIELDS)
PAIR=re.compile(rb"^(NAME|DESCRIPTION|DATE|STATE|HOST|USER)=([\x20-\x7e]{1,240})$")
MAX_GAP=128

def collect(buf):
    results=[]
    for match in re.finditer(rb"(NAME=[\x20-\x7e]{1,240})\x00",buf):
        at=match.start(1)
        # QNX build strings may carry a printable compiler-identification prefix.
        # Do not require the byte before NAME to be NUL.
        name=match.group(1)[5:].decode("ascii")
        cursor=match.end(1)+1
        fields={"NAME":name}
        field_offsets={"NAME":hex(at)}
        # Read contiguous NUL-terminated text fields, no cross-record look-ahead.
        for _ in range(16):
            if cursor>=len(buf):break
            if buf[cursor]==0:
                cursor+=1
                if cursor>=len(buf) or buf[cursor]==0:break
            tail=buf.find(b"\x00",cursor,min(len(buf),cursor+256))
            if tail<0:break
            item=PAIR.fullmatch(buf[cursor:tail])
            if not item or item.group(1)==b"NAME":break
            k=item.group(1).decode("ascii")
            fields[k]=item.group(2).decode("ascii")
            field_offsets[k]=hex(cursor)
            cursor=tail+1
        results.append({"start":hex(at),"end":hex(cursor),"fields":fields,
                        "field_offsets":field_offsets})
    return results

def associate(buf):
    records=collect(buf)
    elfs=sorted(e["at"] for e in scan_elf(buf) if e["strict_elf_valid"])
    items=[]
    for record in records:
        pos=int(record["start"],16)
        i=bisect.bisect_right(elfs,pos)-1
        prev=elfs[i] if i>=0 else None
        nxt=elfs[i+1] if i+1<len(elfs) else None
        # Avoid unqualified ownership claims; keep explicit position only.
        items.append({**record,
            "preceding_elf":hex(prev) if prev is not None else None,
            "distance_from_elf":pos-prev if prev is not None else None,
            "next_elf":hex(nxt) if nxt is not None else None})
    coverage={hex(at):[x["fields"]["NAME"] for x in items
                       if x["preceding_elf"]==hex(at)] for at in elfs}
    return {"strict_elf_count":len(elfs),"records":items,
            "names_by_preceding_elf":coverage,
            "record_count":len(items),
            "warning":"Record boundaries and attribution are provisional. Nearby records may belong to distinct ELF objects."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    if raw[:3]!=b"HSP":raise ValueError("Expected HSP")
    buf,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error:raise ValueError(error)
    output=json.dumps({"decoded_length":len(buf),"encoded_stop":hex(stop),**associate(buf)},indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
