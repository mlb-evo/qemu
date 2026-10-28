# Unresolved IHmiKss callback identities: non-duplicate investigation plan

## Prior work checked before adding this tool

| Existing work | Already established | Not repeated here |
| --- | --- | --- |
| `scan_rte_dp_writes.py` | Direct `BL 0x131390`, literal DP and payload load scanner | No new DP discovery claim |
| `group_rte_dp_callbacks.py` | Nearest preceding ARM `STMDB sp!,{...,lr}` candidate function grouping | No claim to discover grouping |
| `name_rte_dp_callbacks.py` | `batchLock() failed` callback name search in a restricted diagnostic address range | No claim that diagnostic naming is new |
| `export_ipc_dp_table.py` | 176-row canonical source CSV, including 12 `unknown` entries | Canonical CSV unchanged |
| `audit_ipc_callback_layouts.py` | Offset overlap and minimum read extent by callback label | Not a callback identity resolver |

## Incremental contribution

`triage_unresolved_callback_functions.py` is a **function-level evidence ledger**:

1. Groups scanner write sites by candidate ARM function start and emits **start/end VAs** and every DP write VA per group.
2. Searches PC-relative literal pointers for printable NUL-terminated diagnostics **across the available image**, rather than requiring the pointer to lie in `0x88e000–0x88f800`.
3. Preserves the diagnostic source instruction VA, target string VA and string text for review.
4. Reports `unique-diagnostic`, `conflicting-diagnostics`, or `no-name-diagnostic` instead of silently choosing one name.
5. Never edits `gtf2-ipc-to-dp.csv` or claims an original IPC field identifier.

### Reproduce on original stock ELF

```sh
python3 tools/fpk1/research/gtf2/triage_unresolved_callback_functions.py \
  /path/to/STAGE2.1/bin/gtf2 --expect-stock-count \
  --output /tmp/gtf2-callback-function-evidence.csv
```

Compare `dp_ids` in this output to the 12 `unknown` rows in `docs/fpk1/gtf2-ipc-to-dp.csv`. The expected result is a **review queue**, not an automatically trusted rename. A `unique-diagnostic` label still needs confirmation that the string is from the actual callback function and not a nested helper or unrelated literal.

### Open issues and false-positive controls

- The nearest-prologue grouping remains **heuristic**. Nonstandard prologues, inlined code and compiler-generated thunks may cause incorrect boundaries.
- A string pointer inside a function is evidence of a reference, not proof the diagnostic executes along the DP write path.
- Printable diagnostic strings may include unrelated code messages; only the exact `Name(): batchLock() failed` signature becomes a candidate callback name.
- The tool's candidate end bound is the next matching prologue or 0x800 bytes, whichever comes first; it is **not** a verified function size.
- Payload layout and actual wire message length remain unknown.

## Evidence status

This change was reviewed against the existing repository scripts and CSV. **The new triage tool has not been run on the stock GTF2 ELF in this change.** Consequently, it reports no new recovered callback names or additional confirmed DP mappings yet.
