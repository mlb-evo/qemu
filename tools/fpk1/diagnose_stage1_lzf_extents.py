#!/usr/bin/env python3
"""Diagnose LZF suffix endings and ELF PT_LOAD extents in FPK1 Stage1.

Read-only, no decompressed firmware exported. Distinguishes EOF-in-literal
from a verified compressed-block end; diagnoses header/segment sizes.
"""
import argparse,json,struct,zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import STARTS,decode,scan_elf

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        members=[x for x in z.namelist() if x.endswith("/stage1_ifs.img")]
        if len(members)!=1:raise ValueError("Stage1 primary missing/ambiguous")
        data=z.read(members[0])[0xc2:]
    rows=[]
    for start in STARTS:
        decoded,stop,error=decode(data,start)
        elves=scan_elf(decoded)
        rows.append({
            "start":hex(start),"encoded_stop":hex(stop),
            "encoded_remaining":len(data)-stop,"last_encoded_32":data[max(0,stop-32):stop].hex(),
            "decoded_length":len(decoded),"decode_error":error,
            "elfs":[{
                "decoded_offset":hex(e["at"]),"pt_load_count":e["pt_load"],
                "max_load_file_end":e["max_load_file_end"],
                "available_from_elf":len(decoded)-e["at"],
                "missing_bytes_for_max_load_end":max(0,e["max_load_file_end"]-(len(decoded)-e["at"])),
                "all_pt_load_present":e["all_pt_load_present"],
                "all_pt_load_size_ok":e["all_pt_load_size_ok"]
            } for e in elves]
        })
    report={"inner_size":len(data),"method":"LZF suffix decoding; unknown real stream boundaries",
            "caution":"truncated literal at physical EOF is not validated stream terminator",
            "results":rows}
    output=json.dumps(report,indent=2)+"\n"
    print(output,end="")
    if args.json:args.json.write_text(output)
if __name__=="__main__":main()
