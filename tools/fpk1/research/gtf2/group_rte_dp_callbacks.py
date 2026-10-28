#!/usr/bin/env python3
"""Group direct GTF2 RTE->DP writes by ARM function prologue.

Uses the conservative field-site scanner. Group start is the nearest preceding
STMDB sp!,{...,lr} in the callback range. These are *candidate* boundaries:
inspect any unusual function before assigning an IHmiKss method name.
"""
import argparse
import csv
import struct
import sys
from pathlib import Path

from scan_rte_dp_writes import scan, BASE, START

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    p.add_argument("--csv",action="store_true")
    a=p.parse_args()
    data=a.elf.read_bytes()
    if data[:6]!=b"\x7fELF\x01\x01":p.error("expected ARM ELF32 little endian")
    def word(va):return struct.unpack_from("<I",data,va-BASE)[0]
    grouped={}
    for call,dp,width,offset,literal in scan(data):
        addr=int(call,16)
        start=next((x for x in range(addr-4,max(START,addr-0x800),-4)
                    if word(x)&0xffff4000==0xe92d4000),None)
        if start is None:raise ValueError(f"no nearby function prologue at {call}")
        grouped.setdefault(start,[]).append((call,dp,width,offset))
    rows=[]
    for start,items in sorted(grouped.items()):
        for call,dp,width,offset in items:
            rows.append((f"0x{start:08x}",call,dp,width,offset,len(items)))
    if a.csv:
        writer=csv.writer(sys.stdout)
        writer.writerow(("candidate_callback_va","call_va","dp_id","width","payload_offset","callback_site_count"))
        writer.writerows(rows)
    else:
        for start,items in sorted(grouped.items()):
            print(f"0x{start:08x}: {len(items):2d} direct DP writes, "
                  f"first={items[0][0]}, last={items[-1][0]}")
        print(f"TOTAL {len(grouped)} candidate callback functions, {len(rows)} DP write sites")
if __name__=="__main__":main()
