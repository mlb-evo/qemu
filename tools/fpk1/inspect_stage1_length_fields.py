#!/usr/bin/env python3
"""Inspect Stage1 HSP/inner length fields and LZF trailer hypotheses.

Read-only. No interpretation of unknown header fields is assumed.
"""
import argparse,json,struct,zipfile
from pathlib import Path

def words(data,begin,end):
    return [{"offset":hex(i),"u32le":hex(struct.unpack_from("<I",data,i)[0])}
            for i in range(begin,min(end,len(data)-3),4)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path);ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        paths=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(paths)!=1:raise ValueError("Ambiguous primary Stage1")
        raw=z.read(paths[0])
    if raw[:3]!=b"HSP":raise ValueError("Expected HSP")
    inner=raw[0xc2:]; end=0x1f6ffb
    declared=struct.unpack_from("<I",inner,0)[0]
    hits=[]
    for target in (len(raw),len(inner),declared,end,end-0x800,len(inner)-end):
        matches=[]
        for base,label in ((raw,"raw"),(inner,"inner")):
            for i in range(0,min(len(base)-3,0x1000),4):
                if struct.unpack_from("<I",base,i)[0]==target:
                    matches.append({"space":label,"at":hex(i)})
        hits.append({"value":hex(target),"locations":matches[:20]})
    result={
      "raw_length":len(raw),"inner_length":len(inner),
      "declared_inner_header_u32le":hex(declared),
      "declared_plus_wrapper":hex(declared+0xc2),
      "end_of_full_token_sequence":hex(end),
      "declared_minus_end":declared-end,
      "inner_minus_declared":len(inner)-declared,
      "inner_minus_token_end":len(inner)-end,
      "tail_after_end_hex":inner[end:].hex(),
      "raw_hsp_header_0x0_0xc2":raw[:0xc2].hex(),
      "inner_first_0x100":inner[:0x100].hex(),
      "inner_last_0x40":inner[-64:].hex(),
      "candidate_header_equalities":hits,
      "note":"Field values and coincidences are observations, not validated HSP/IFS field meanings."}
    txt=json.dumps(result,indent=2)+"\n";print(txt,end="")
    if a.json:a.json.write_text(txt)
if __name__=="__main__":main()
