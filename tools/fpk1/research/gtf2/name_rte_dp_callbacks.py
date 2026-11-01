#!/usr/bin/env python3
"""Attach verified IHmiKss callback names to RTE-to-DP writes.

Uses diagnostic string pointers referenced by each ARM callback function.
Unidentified callbacks remain explicitly unnamed; do not guess their names.
"""
import argparse
import csv
import re
import struct
import sys
from pathlib import Path
from scan_rte_dp_writes import scan, BASE, START

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    p.add_argument("--csv",action="store_true")
    args=p.parse_args()
    data=args.elf.read_bytes()
    if data[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little endian")
    def word(a):return struct.unpack_from("<I",data,a-BASE)[0]
    groups={}
    for call,dp,width,offset,literal in scan(data):
        addr=int(call,16)
        start=next((x for x in range(addr-4,max(START,addr-0x800),-4)
                    if word(x)&0xffff4000==0xe92d4000),None)
        if start is None:raise ValueError(f"no function prologue for {call}")
        groups.setdefault(start,[]).append((call,dp,width,offset))
    def name(start):
        end=next((x for x in range(start+4,min(start+0x800,0x6a0000),4)
                  if word(x)&0xffff4000==0xe92d4000),start+0x800)
        for a in range(start,end,4):
            ins=word(a)
            if ins&0x0f7f0000!=0x051f0000:continue
            literal=a+8+(ins&4095 if ins&0x800000 else -(ins&4095))
            if not BASE<=literal<=BASE+len(data)-4:continue
            ptr=word(literal)
            if not 0x88e000<=ptr<0x88f800:continue
            raw=data[ptr-BASE:ptr-BASE+160].split(b"\0")[0]
            m=re.match(rb"([A-Za-z0-9_]+)\(\): batchLock\(\) failed",raw)
            if m:return m.group(1).decode("ascii")
        return "unidentified"
    rows=[]
    for start,items in sorted(groups.items()):
        for call,dp,width,offset in items:
            rows.append((f"0x{start:08x}",name(start),call,dp,width,offset))
    if args.csv:
        writer=csv.writer(sys.stdout)
        writer.writerow(("callback_va","callback_name","write_va","dp_id","width","payload_offset"))
        writer.writerows(rows)
    else:
        named=0
        for start,items in sorted(groups.items()):
            label=name(start)
            if label!="unidentified":named+=1
            print(f"0x{start:08x} {label:<32} {len(items):2d} DP writes")
        print(f"TOTAL {len(groups)} groups, {named} named, {len(rows)} direct writes")
if __name__=="__main__":main()
