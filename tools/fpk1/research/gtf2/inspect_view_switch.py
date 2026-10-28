#!/usr/bin/env python3
"""Resolve GTF2 ARM literal-pool pointers to local ELF strings.

Uses only original executable PT_LOAD VA-to-file mapping. No firmware copied.
"""
import argparse
import json
import struct
from pathlib import Path

BASE = 0x100000
POOL_SITES = {
    0x6a9324: "BaseViewManager::handleViewSwitch",
    0x6a9328: "logger object pointer (not a string)",
    0x6a932c: "handleViewSwitch",
    0x6a9330: "handleViewSwitch: %p",
    0x119a48: "doSwitch(), switching off current view",
    0x119a58: "ViewManager::justHidden",
}
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    args = p.parse_args()
    data = args.elf.read_bytes()
    if data[:4] != b"\x7fELF":
        raise SystemExit("Not ELF")
    rows = []
    for site, note in POOL_SITES.items():
        value = struct.unpack_from("<I", data, site-BASE)[0]
        offset = value-BASE
        raw = data[offset:offset+180].split(b"\0", 1)[0] if 0 <= offset < len(data) else b""
        text = raw.decode("utf-8", errors="replace") if raw and all(32 <= c < 127 for c in raw) else None
        rows.append({"pool_va":hex(site),"value_va":hex(value),"string":text,"expected":note})
    print(json.dumps(rows, indent=2))
if __name__ == "__main__":
    main()
