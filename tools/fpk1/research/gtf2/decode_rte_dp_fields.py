#!/usr/bin/env python3
"""Extract verified GTF2 IHmiKss callback payload-field -> DP-ID mappings.

Reads ARM LDR literal/field-load instructions from the original executable,
rather than guessing names from the diagnostics. Extend SITES only after
checking each callback's disassembly.
"""
import argparse
import struct
from pathlib import Path

BASE=0x100000
SITES={
    "TCH_HMI_EngineRPM":[(0x697290,0x697294),(0x6972a4,0x6972a8)],
    "Gear_Display":[
        (0x69538c,0x695390),(0x6953a0,0x6953a4),
        (0x6953b0,0x6953b4),(0x6953c4,0x6953c8),
        (0x6953d8,0x6953dc),(0x6953ec,0x6953f0),
        (0x695400,0x695404),(0x695414,0x695418),
        (0x695428,0x69542c),(0x69543c,0x695440),
        (0x695450,0x695454)],
}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("elf",type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little endian")
 def word(va):return struct.unpack_from("<I",b,va-BASE)[0]
 for name,sites in SITES.items():
  print(name)
  for literal_load,field_load in sites:
   ins=word(literal_load)
   if ins&0x0f7f0000!=0x051f0000:raise ValueError(f"not PC-relative literal load: {literal_load:x}")
   addr=literal_load+8+(ins&0xfff if ins&0x800000 else -(ins&0xfff))
   dp=word(addr)
   field=word(field_load)
   if (field&0x0ff000f0)==0x01d000b0:width="u16";offset=(field&0xf)|((field>>4)&0xf0)
   elif (field&0x0ff00000)==0x05d00000:width="u8";offset=field&0xfff
   else:raise ValueError(f"unexpected payload load {field_load:x}: {field:08x}")
   print(f"  payload+0x{offset:02x} {width} -> DP 0x{dp:08x} (code 0x{literal_load:x})")
if __name__=="__main__":main()
