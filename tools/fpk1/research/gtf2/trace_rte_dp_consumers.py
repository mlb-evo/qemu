#!/usr/bin/env python3
"""Find exact ARM PC-relative LDR xrefs to DP IDs written by GTF2 RTE callbacks.

References are not necessarily value reads: some compare IDs or initialize
subscription metadata. The CSV distinguishes code locations, not semantics.
"""
import argparse, collections, csv, struct, sys
from pathlib import Path
from scan_rte_dp_writes import scan

BASE=0x100000
CODE_END=0xa634dc

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    p.add_argument("--csv",action="store_true")
    a=p.parse_args()
    data=a.elf.read_bytes()
    if data[:6]!=b"\x7fELF\x01\x01":p.error("expected little-endian ELF32")
    def word(va):return struct.unpack_from("<I",data,va-BASE)[0]
    incoming={}
    for call,dp,width,offset,lit in scan(data):
        incoming[int(dp,16)]=(call,width,offset)
    literals=collections.defaultdict(list)
    for off in range(0,len(data)-3,4):
        value=struct.unpack_from("<I",data,off)[0]
        if value in incoming:literals[BASE+off].append(value)
    rows=[]
    for va in range(BASE,CODE_END-3,4):
        ins=word(va)
        if ins&0x0f7f0000!=0x051f0000:continue
        addr=va+8+(ins&4095 if ins&0x800000 else -(ins&4095))
        for dp in literals.get(addr,()):
            if 0x694000<=va<0x698000:continue
            call,width,offset=incoming[dp]
            region=("view/HMI-code" if 0x550000<=va<0x630000
                    else "initialization" if 0x210000<=va<0x230000
                    else "other")
            rows.append((f"0x{dp:08x}",call,width,offset,
                         f"0x{va:08x}",f"0x{addr:08x}",region))
    if a.csv:
        writer=csv.writer(sys.stdout)
        writer.writerow(("dp_id","ipc_writer_va","field_width","payload_offset",
                         "xref_instruction_va","xref_literal_va","xref_region"))
        writer.writerows(rows)
    else:
        counts=collections.Counter(row[-1] for row in rows)
        print(f"{len(incoming)} incoming DP IDs, {len(rows)} non-writer xrefs")
        for region,n in sorted(counts.items()):print(f"  {region}: {n}")
        for dp in (0x02000293,0x02000295,0x020001f7,0x020001f9):
            uses=[r[4] for r in rows if r[0]==f"0x{dp:08x}"]
            print(f"0x{dp:08x}: {', '.join(uses)}")
if __name__=="__main__":main()
