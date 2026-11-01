#!/usr/bin/env python3
"""Audit IHmiKss IPC->DP CSV and derive conservative callback payload read bounds.

CSV-only audit; does not assert actual IPC message sizes or callback identity for
rows labelled 'unknown'. Re-run export_ipc_dp_table.py against the stock ELF
to verify the binary provenance of the input CSV.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

def parse(path):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"ipc_interface", "callback", "ipc_field_offset",
                    "field_read_type", "dp_id", "dp_write_call_va"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns: " + ", ".join(sorted(required - set(reader.fieldnames or []))))
        rows = list(reader)
    for row in rows:
        row["offset"] = int(row["ipc_field_offset"], 16)
        row["width_bytes"] = {"u8": 1, "u16": 2}[row["field_read_type"]]
        row["end"] = row["offset"] + row["width_bytes"]
        if row["offset"] < 0 or row["end"] > 65536:
            raise ValueError("Invalid offset/width: " + repr(row))
    return rows

def audit(rows):
    if len({r["dp_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate DP IDs")
    groups = defaultdict(list)
    for row in rows:
        groups[row["callback"]].append(row)
    summary = []
    for callback, records in sorted(groups.items()):
        occupied = {}
        overlaps = []
        for record in records:
            for byte in range(record["offset"], record["end"]):
                if byte in occupied:
                    overlaps.append((byte, occupied[byte], record["dp_id"]))
                occupied[byte] = record["dp_id"]
        summary.append(dict(callback=callback, dp_count=len(records),
                            min_readable_bytes=max(r["end"] for r in records),
                            overlaps=len(overlaps),
                            identity="unresolved" if callback == "unknown" else "named",
                            **{"_overlap_details": overlaps}))
    return summary

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path)
    p.add_argument("--output", type=Path, help="Write derived callback layout CSV")
    p.add_argument("--expect-stock-count", action="store_true",
                   help="Require current stock export: 176 DP rows")
    args = p.parse_args()
    rows = parse(args.csv)
    if args.expect_stock_count and len(rows) != 176:
        raise ValueError(f"Expected 176 rows, got {len(rows)}")
    result = audit(rows)
    named_overlap = [r for r in result if r["identity"] == "named" and r["overlaps"]]
    if named_overlap:
        raise ValueError("Named callbacks contain overlapping field reads: " + repr(named_overlap))
    print(f"DP rows: {len(rows)}; callback labels: {len(result)}; named: {sum(r['identity']=='named' for r in result)}")
    for row in result:
        print(f"{row['callback']}: {row['dp_count']} DPs, observed read extent {row['min_readable_bytes']} bytes, overlaps {row['overlaps']}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["callback", "dp_count", "min_readable_bytes", "overlaps", "identity"])
            writer.writeheader()
            writer.writerows({k: v for k, v in r.items() if not k.startswith("_")} for r in result)
    if any(r["callback"] == "unknown" for r in result):
        print("CAUTION: 'unknown' combines unresolved callback identities; its read extent is NOT a message schema.")

if __name__ == "__main__":
    main()
