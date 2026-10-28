#!/usr/bin/env python3
"""Recover unresolved IHmiKss callback *function identities*, not IPC field names.

Unlike name_rte_dp_callbacks.py this emits a function-level evidence ledger,
scans all NUL-terminated diagnostic strings referenced by PC-relative ARM LDRs
(not just the narrow batchLock address range), and detects conflicting names.
An inferred name is NEVER silently promoted into the canonical IPC->DP CSV.
"""
import argparse
import csv
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path
from scan_rte_dp_writes import scan, BASE, START, END

PROLOGUE_MASK = 0xffff4000
PROLOGUE_VALUE = 0xe92d4000
NAME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]{1,80})\(\): batchLock\(\) failed")
PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{8,160}\x00")

def recover(data, max_function_bytes=0x800):
    def word(va):
        if va < BASE or va + 4 > BASE + len(data):
            raise ValueError("Address outside ELF image: 0x%x" % va)
        return struct.unpack_from("<I", data, va - BASE)[0]

    starts = [va for va in range(START, END, 4)
              if word(va) & PROLOGUE_MASK == PROLOGUE_VALUE]
    if not starts:
        raise ValueError("No ARM function prologues found")
    sites = defaultdict(list)
    for call, dp, width, offset, _ in scan(data):
        va = int(call, 16)
        preceding = [s for s in starts if s <= va]
        if not preceding:
            raise ValueError("No function prologue before " + call)
        start = preceding[-1]
        if va - start > max_function_bytes:
            raise ValueError("Write too far from candidate function start: " + call)
        sites[start].append((call, dp, width, offset))
    rows = []
    for start, writes in sorted(sites.items()):
        later = next((s for s in starts if s > start), END)
        end = min(later, start + max_function_bytes)
        refs = []
        names = set()
        for va in range(start, end, 4):
            ins = word(va)
            if ins & 0x0f7f0000 != 0x051f0000:
                continue
            address = va + 8 + ((ins & 0xfff) if ins & 0x800000 else -(ins & 0xfff))
            if address < BASE or address + 4 > BASE + len(data):
                continue
            pointer = word(address)
            if pointer < BASE or pointer >= BASE + len(data):
                continue
            raw = data[pointer-BASE:pointer-BASE+161]
            match = PRINTABLE_RE.match(raw)
            if not match:
                continue
            diagnostic = match.group(0)[:-1].decode("ascii")
            refs.append((va, pointer, diagnostic))
            named = NAME_RE.match(diagnostic)
            if named:
                names.add(named.group(1))
        status = ("unique-diagnostic" if len(names) == 1
                  else "conflicting-diagnostics" if names else "no-name-diagnostic")
        rows.append(dict(callback_start_va=f"0x{start:08x}",
                         candidate_end_va=f"0x{end:08x}",
                         identity_status=status,
                         candidate_name=next(iter(names)) if len(names)==1 else "",
                         candidate_names=";".join(sorted(names)),
                         dp_count=len(writes),
                         dp_ids=";".join(w[1] for w in writes),
                         dp_write_vas=";".join(w[0] for w in writes),
                         diagnostic_references=" | ".join(
                             f"0x{va:x}->0x{ptr:x}:{msg}" for va,ptr,msg in refs[:12]),
                         diagnostic_ref_count=len(refs)))
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-stock-count", action="store_true")
    args = parser.parse_args()
    data = args.elf.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01":
        parser.error("Expected little-endian ELF32")
    rows = recover(data)
    if args.expect_stock_count and sum(r["dp_count"] for r in rows) != 176:
        raise ValueError("Expected 176 direct DP write sites")
    writer_target = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(writer_target, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    finally:
        if args.output:
            writer_target.close()
    counts = defaultdict(int)
    for row in rows:
        counts[row["identity_status"]] += 1
    print("Function candidates: %d; status: %s" % (len(rows), dict(counts)), file=sys.stderr)
    print("Names are diagnostic-derived candidates, not independently verified IPC method declarations.", file=sys.stderr)

if __name__ == "__main__":
    main()
