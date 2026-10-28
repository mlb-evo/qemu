# IHmiKss callback payload read-bound audit

Derived from `docs/fpk1/gtf2-ipc-to-dp.csv`, **not** from a fresh ELF run. The underlying table's ARM provenance is checked by `export_ipc_dp_table.py` when supplied the original GTF2 binary.

## New observations

- **176 distinct DP IDs** across **34 callback labels**: 33 named callbacks and one unresolved label `unknown` containing 12 DP rows.
- All **33 named callback groups** have non-overlapping byte ranges among their exported reads. This does not prove that their payloads contain only those fields.
- The `unknown` aggregate has **5 byte-overlap occurrences**. It is **not one verified IPC callback**, and its apparent 20-byte read extent **must not be used** as a message schema.
- The largest observed named callback read extent is **22 bytes**, for `Config_Installation_Coding`. This is a *minimum readable extent*, not an asserted C struct size or wire length.
- Field offsets refer to the callback payload pointer inferred by the existing exporter; packing, endianness of the IPC transport, nested structures, and omitted fields are not established by this audit.

## Implementation consequence

For an IAA replacement, dispatch on the **real callback identity**, not solely on DP ID or the placeholder `unknown`. Each named callback can be represented by an observed sparse set of offset/width reads, but the decoder must validate incoming payload length against the highest accessed end offset and must not assume that the computed lower bound equals the full IPC message size.

The 12 unresolved rows need a **binary-backed recovery of callback function boundaries and their names** before implementing their transport decoding. Grouping them under one callback would produce ambiguous overlapping fields.

## Reproduce

```sh
python3 tools/fpk1/research/gtf2/audit_ipc_callback_layouts.py docs/fpk1/gtf2-ipc-to-dp.csv --expect-stock-count --output docs/fpk1/gtf2-ipc-callback-read-bounds.csv
```

The derived CSV is an **analysis artifact**, not a stock IPC ABI specification.
