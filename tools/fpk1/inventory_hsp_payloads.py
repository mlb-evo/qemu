#!/usr/bin/env python3
"""Classify FPK1 HSP-wrapped files without assuming one payload format.

Read-only; compares structural traits, not proprietary decryption.
"""
import argparse
import json
import struct
import zipfile
from pathlib import Path

FOOTER=bytes.fromhex("6865500e01000000")
def inspect(name,raw):
    if not raw.startswith(b"HSP"):
        return None
    data=raw[0xc2:]
    result={"name":name,"hsp_payload_bytes":len(data),
            "common_footer":data.endswith(FOOTER)}
    if len(data)>=0x800:
        result.update(
            word0=f"0x{struct.unpack_from('<I',data,0)[0]:08x}",
            word4=f"0x{struct.unpack_from('<I',data,4)[0]:08x}",
            mode_0x258=struct.unpack_from("<I",data,0x258)[0],
            field_0x25c=f"0x{struct.unpack_from('<I',data,0x25c)[0]:08x}",
            area_0x7f4=data[0x7f4:0x800].hex(),
            first_8_at_0x800=data[0x800:0x808].hex(),
            qnx_magic_at=data.find(bytes.fromhex("eb7eff00")),
            imagefs_at=data.find(b"imagefs"))
        declared=struct.unpack_from("<I",data,0)[0]
        # A length that merely fits is insufficient: stage2_nand is a
        # known counterexample. Confirm the shared IFS header and all bytes
        # after the declared end through the footer are zero.
        end = 0x800 + declared
        has_common_header = struct.unpack_from("<I", data, 4)[0] == 0x00a00800
        plausible_length = 0x800 <= end <= len(data)-8
        padding_is_zero = (plausible_length and
                           not any(data[end:-8]))
        result["length_relation"] = plausible_length
        result["ifs_container_candidate"] = (
            has_common_header and plausible_length and padding_is_zero
            and data.endswith(FOOTER))
        if plausible_length:
            result["declared_end"]=f"0x{end:x}"
            result["zero_bytes_from_declared_end_to_footer"]=(
                len(data)-8-end if padding_is_zero else None)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        results=[v for n in z.namelist() if n.endswith((".img",".bin"))
                 if (v:=inspect(n,z.read(n))) is not None]
    rendered=json.dumps(results,indent=2)+"\n"
    print(rendered,end="")
    if a.json:a.json.write_text(rendered)
if __name__=="__main__":
    main()
