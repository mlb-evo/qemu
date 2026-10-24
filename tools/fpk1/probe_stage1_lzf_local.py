#!/usr/bin/env python3
"""Validate isolated LZF grammar at Stage1's repeated runs.

Starts with a *hypothetical* one-byte zero decode history, only to test
whether immediately following tokens reconstruct an ELF32 header. This does
not establish an actual stream boundary or original preceding byte.
"""
import argparse,json,struct,zipfile
from pathlib import Path
PAT=b"\xe0\xff\x00"

def decode_prefix(src, seed=b"\x00", cap=16384):
    out=bytearray(seed);p=0
    try:
        while p<len(src) and len(out)<cap:
            c=src[p];p+=1
            if c<32:
                n=c+1
                if p+n>len(src):raise ValueError("truncated literal")
                out.extend(src[p:p+n]);p+=n
            else:
                n=c>>5
                if n==7:
                    if p>=len(src):raise ValueError("truncated length")
                    n+=src[p];p+=1
                if p>=len(src):raise ValueError("truncated distance")
                dist=((c&31)<<8)+src[p]+1;p+=1
                n+=2
                if dist>len(out):raise ValueError("invalid backreference")
                if len(out)+n>cap:break
                if dist==1:out.extend(bytes([out[-1]])*n)
                else:
                    for _ in range(n):out.append(out[-dist])
        return bytes(out[len(seed):]),p,None
    except ValueError as e:return bytes(out[len(seed):]),p,str(e)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        matches=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(matches)!=1:raise ValueError("Ambiguous Stage1")
        data=z.read(matches[0])[0xc2:]
    rows=[];p=0
    while (p:=data.find(PAT,p))>=0:
        start=p
        while data[p:p+3]==PAT:p+=3
        count=(p-start)//3
        if count<4:
            p=start+1
            continue
        # LZF token grammar test with a synthetic history byte, not actual decompression.
        decoded,consumed,err=decode_prefix(data[start:start+65536])
        idx=decoded.find(b"\x7fELF")
        plausible=False
        if idx>=0 and idx+52<=len(decoded):
            h=decoded[idx:idx+52]
            plausible=(h[:7]==b"\x7fELF\x01\x01\x01" and
                       struct.unpack_from("<H",h,18)[0]==40 and
                       struct.unpack_from("<I",h,20)[0]==1 and
                       struct.unpack_from("<H",h,40)[0]==52)
        rows.append({"run_at":hex(start),"triples":count,
                     "decoded_prefix_bytes":len(decoded),"consumed_encoded_bytes":consumed,
                     "first_elf_at_decoded_offset":idx if idx>=0 else None,
                     "plausible_elf32_arm":plausible,"error":err,
                     "decoded_at_elf_52":decoded[idx:idx+52].hex() if idx>=0 else None})
    result={"total_runs":len(rows),"runs_with_decoded_elf_magic":sum(r["first_elf_at_decoded_offset"] is not None for r in rows),
            "runs_with_plausible_elf32_arm":sum(r["plausible_elf32_arm"] for r in rows),
            "method":"Synthetic zero byte seeded output history; this is a local grammar test, not full image decompression",
            "results":rows}
    out=json.dumps(result,indent=2)+"\n"
    print(out,end="")
    if args.json:args.json.write_text(out)
if __name__=="__main__":main()
