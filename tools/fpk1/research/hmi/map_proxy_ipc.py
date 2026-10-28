#!/usr/bin/env python3
"""Extract both 180-entry proxy dispatch tables from llvm-objdump output.

Usage: python3 tools/fpk1/research/hmi/map_proxy_ipc.py proxy.dis OUTDIR
Output is a *structural* index-to-branch map, not decoded wire payload.
"""
import csv
import pathlib
import re
import sys

disassembly = pathlib.Path(sys.argv[1]).read_text().splitlines()
outdir = pathlib.Path(sys.argv[2])
outdir.mkdir(parents=True, exist_ok=True)
instructions = {}
for line in disassembly:
    match = re.match(r"^\s*([0-9a-f]+):\s+[0-9a-f]{8}\s+(.+)", line)
    if match:
        instructions[int(match[1], 16)] = match[2]

def decode_table(start):
    result = []
    for index in range(180):
        pc = start + index * 4
        match = re.search(r"\bb\s+0x([0-9a-f]+)", instructions.get(pc, ""))
        if not match:
            raise ValueError(f"No branch at table entry {index}: {pc:#x}")
        result.append(int(match[1], 16))
    return result

for name, start in (("incoming", 0x40ca8), ("outgoing", 0x3d7a0)):
    targets = decode_table(start)
    boundaries = sorted(set(targets))
    output = outdir / f"proxy_{name}_180.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["dispatch_index", "table_entry", "branch_target",
                         "next_case_start_approx", "linear_window_instructions",
                         "possible_receiver_virtual_slots_NOT_CFG_VERIFIED"])
        for index, target in enumerate(targets):
            pos = boundaries.index(target)
            upper = boundaries[pos + 1] if pos + 1 < len(boundaries) else (
                0x50100 if name == "incoming" else 0x40b80)
            window = [(pc, instructions[pc]) for pc in sorted(instructions)
                      if target <= pc < upper]
            possible = []
            for j, (pc, opcode) in enumerate(window):
                if re.search(r"\bblx\s+r[0-9]+", opcode):
                    for earlier_pc, earlier_opcode in window[max(0, j-10):j]:
                        found = re.search(
                            r"\bldr\s+r[0-9]+,\s*\[r[0-9]+,\s*#0x([0-9a-f]+)\]",
                            earlier_opcode)
                        if found and int(found[1], 16) >= 0x60:
                            possible.append(f"{earlier_pc:#x}:{int(found[1],16)//4}")
            writer.writerow([index, f"{start + index*4:#x}", f"{target:#x}",
                             f"{upper:#x}", len(window), ";".join(possible[:8])])
    print(f"{name}: 180 indices, {len(set(targets))} unique targets, {output}")

# The linear-window heuristic is NOT a control-flow graph. Its candidate virtual
# slots must be confirmed with register dataflow before implementation.
