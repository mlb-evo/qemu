#!/usr/bin/env python3
"""Inventory GTF2-owned IPC service names, lifecycle callbacks and RTE handlers.

Reads the original ELF bytes only; no firmware data is committed. String
evidence identifies handlers, but does not prove each handler is invoked.
"""
import argparse
import re
from pathlib import Path

BASE = 0x100000
RANGES = [(0x88d800, 0x88e320), (0x88ec00, 0x88f600), (0x7d9400, 0x7da300)]
NEEDLES = (
    "asi.gss.", "ReplyImpl::", "batchLock() failed", "handleKeyEventMfl",
    "handleKeyEventMmi", "received MMI", "MFL keycode", "rteTimeout",
    "rteNoInit", "lost server connection", "GSS_IPC_", "GSS_HMI_State",
)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("elf", type=Path)
    args = p.parse_args()
    data = args.elf.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        p.error("expected ELF32 little endian")
    for start, stop in RANGES:
        for match in re.finditer(rb"[\x20-\x7e]{7,}", data[start-BASE:stop-BASE]):
            value = match.group().decode("ascii")
            if any(needle in value for needle in NEEDLES):
                print(f"0x{start+match.start():08x} {value}")
if __name__ == "__main__":
    main()
