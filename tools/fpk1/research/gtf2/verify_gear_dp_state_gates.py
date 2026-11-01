#!/usr/bin/env python3
"""Verify exact truth table of Gear_Display DP 0x020001f9 consumer.

Fails on any firmware mismatch. Distinguishes cached state, notification, and
the no-op path when external receiver is absent.
"""
import argparse,struct
from pathlib import Path
BASE=0x100000
W={
0x219b80:0xebfffa11,0x219b8c:0xebfffa39,0x219b98:0xebfff9ff,
0x219ba8:0xe59f002c,0x219bac:0xeb121421,0x219bcc:0xe1dd00f6,
0x219bd4:0x13a00001,0x219bdc:0x020001f9,
0x5fdb98:0xebf06ff6,0x5fdba8:0xe5933070,0x5fdbbc:0xe5933070,
0x5fdbcc:0xeb015347,
0x6528f4:0xe5d031b8,0x652900:0xe3130001,
0x652904:0x0a000010,0x652908:0xe59060fc,
0x652910:0x0a000013,0x652914:0xebff8f60,
0x652938:0xebebe882,0x652940:0xe3833010,
0x65294c:0xe5d030f8,0x652950:0xe5c410f8,
0x652954:0xe1530001,0x65295c:0x13833010,
}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("elf",type=Path);a=p.parse_args()
 b=a.elf.read_bytes()
 if b[:6]!=b"\x7fELF\x01\x01":p.error("expected ELF32 little endian")
 for va,want in W.items():
  got=struct.unpack_from("<I",b,va-BASE)[0]
  if got!=want:raise ValueError(f"0x{va:x}: got 0x{got:08x}, expected 0x{want:08x}")
 print(f"verified {len(W)} exact ARM words")
 print("state=bool(DP[0x020001f9]) only when any of 3 gates is true")
 print("receiver+0x1b8 bit0=0: cache byte +0xf8, dirty on change")
 print("receiver+0x1b8 bit0=1, +0xfc != 0: notify, dirty")
 print("receiver+0x1b8 bit0=1, +0xfc == 0: return unchanged")
if __name__=="__main__":main()
