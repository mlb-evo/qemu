#!/usr/bin/env python3
"""Scan GTF2-owned RTE callbacks for literal DP IDs and direct payload loads.

Conservative pattern: BL 0x131390, nearby PC-relative LDR r1 of a 0x02xxxxxx
DP identifier, and LDRB/LDRH r2 from the incoming payload. Reports only
direct-load matches; computed/transformed fields require separate analysis.
"""
import argparse
import csv
import struct
import sys
from pathlib import Path

BASE=0x100000
START=0x680000
END=0x6a0000
DP_WRITE=0x131390

def scan(data):
    def word(addr):
        return struct.unpack_from("<I",data,addr-BASE)[0]
    for call in range(START,END,4):
        ins=word(call)
        if ins&0x0f000000!=0x0b000000:continue
        delta=ins&0xffffff
        if delta&0x800000:delta-=0x1000000
        if call+8+delta*4!=DP_WRITE:continue
        for back in (8,12,16):
            literal_ins_addr=call-back
            li=word(literal_ins_addr)
            if li&0x0f7f0000!=0x051f0000 or (li>>12)&15!=1:continue
            lit=literal_ins_addr+8+(li&4095 if li&0x800000 else -(li&4095))
            if not BASE<=lit<=BASE+len(data)-4:continue
            dp=word(lit)
            if dp>>24!=2:continue
            for field_ins_addr in range(literal_ins_addr+4,call,4):
                fi=word(field_ins_addr)
                if ((fi>>12)&15)!=2:continue
                if fi&0x0ff00000==0x05d00000:
                    kind="u8";offset=fi&4095
                elif fi&0x0ff000f0==0x01d000b0:
                    kind="u16";offset=(fi&15)|((fi>>4)&240)
                else:continue
                yield (f"0x{call:08x}",f"0x{dp:08x}",kind,f"0x{offset:x}",f"0x{literal_ins_addr:08x}")
                break
            break

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf",type=Path)
    p.add_argument("--csv",action="store_true",help="machine-readable output")
    a=p.parse_args()
    data=a.elf.read_bytes()
    if data[:6]!=b"\x7fELF\x01\x01":p.error("expected ARM ELF32 little endian")
    rows=list(scan(data))
    if a.csv:
        writer=csv.writer(sys.stdout)
        writer.writerow(("call_va","dp_id","field_width","payload_offset","literal_load_va"))
        writer.writerows(rows)
    else:
        for row in rows:print(" ".join(row))
        print(f"total direct field-to-DP mappings: {len(rows)}")
if __name__=="__main__":main()
