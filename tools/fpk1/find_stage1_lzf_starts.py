#!/usr/bin/env python3
"""Find candidate genuine LZF stream starts before known Stage1 ELF markers.

Read-only. Unlike seeded local probes, each candidate starts with EMPTY history.
Decoding must reach the target encoded marker and produce a valid ARM ELF
header. A validated suffix alone does not prove the original chunk boundary.
"""
import argparse,json,struct,zipfile
from pathlib import Path

TARGETS=(0x131913,0x18da01,0xf1bbb,0x112367,0x19421c,0x1c14f8)
MAX_OUTPUT=8*1024*1024

def decode_to(src,start,minimum_end,max_output=MAX_OUTPUT):
    out=bytearray()
    p=start
    while p<len(src) and (p<minimum_end or len(out)<256):
        c=src[p];p+=1
        if c<32:
            n=c+1
            if p+n>len(src) or len(out)+n>max_output:return None
            out.extend(src[p:p+n]);p+=n
        else:
            n=c>>5
            if n==7:
                if p>=len(src):return None
                n+=src[p];p+=1
            if p>=len(src):return None
            dist=((c&31)<<8)+src[p]+1;p+=1
            n+=2
            if dist>len(out) or len(out)+n>max_output:return None
            if dist==1:out.extend(bytes([out[-1]])*n)
            elif dist>=n:out.extend(out[-dist:-dist+n])
            else:
                for _ in range(n):out.append(out[-dist])
    return p,bytes(out)

def valid_arm_header(b,offset):
    if offset+52>len(b):return False
    if b[offset:offset+7]!=b"\x7fELF\x01\x01\x01":return False
    machine,version=struct.unpack_from("<HI",b,offset+18)
    ehsize,phentsize,phnum=struct.unpack_from("<HHH",b,offset+40)
    return machine==40 and version==1 and ehsize==52 and phentsize==32 and 0<phnum<=128

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--lookback",type=int,default=2048,
                    help="Candidate byte offsets preceding each run (default 2048)")
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    if not 1<=a.lookback<=16384:raise ValueError("lookback outside 1..16384")
    with zipfile.ZipFile(a.archive) as z:
        matches=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(matches)!=1:raise ValueError("Missing/ambiguous Stage1")
        raw=z.read(matches[0])
        if raw[:3]!=b"HSP":raise ValueError("Expected HSP envelope")
        data=raw[0xc2:]
    report=[]
    for target in TARGETS:
        if target>=len(data):continue
        plausible=[]
        # Decode beyond the target run until the first complete 52-byte ELF
        # after its encoded literal marker. Output history begins empty.
        required_end=min(len(data),target+1024)
        for start in range(max(0,target-a.lookback),target):
            result=decode_to(data,start,required_end)
            if result is None:continue
            end,decoded=result
            elf=decoded.find(b"\x7fELF")
            if elf<0 or not valid_arm_header(decoded,elf):continue
            plausible.append({"candidate_start":hex(start),
                              "encoded_bytes_consumed":end-start,
                              "decoded_size":len(decoded),
                              "elf_at_decoded_offset":elf})
        report.append({"target_run":hex(target),"lookback":a.lookback,
                       "valid_candidate_count":len(plausible),
                       "candidate_starts":plausible[:30],
                       "candidates_truncated":len(plausible)>30})
    result={"method":"unseeded LZF token decoding from candidate starts before confirmed runs",
            "caution":"A matching suffix does not independently establish stream framing",
            "targets":report}
    output=json.dumps(result,indent=2)+"\n"
    print(output,end="")
    if a.json:a.json.write_text(output)
if __name__=="__main__":main()
