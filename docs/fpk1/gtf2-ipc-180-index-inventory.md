# GTF2 IPC: full dispatch-index inventory methodology

Source: original firmware `libgssIpcRteHmiProxy.so`, ARM32 ELF, SHA256 `188d610c523cbdd1b81ab89420e5fb1042753faeeb7edf9914ae595a449f33a2`.

## Findings

Two independently decoded, 180-entry dispatch tables (0..179) each have **141 distinct branch targets**. Incoming dispatch is `0x40b80`, with table at `0x40ca8`; outgoing construction is `0x3d77c`, with table at `0x3d7a0`. An entry maps an **internal dispatch index** to a branch, not necessarily an on-wire selector or unique callback. Duplicate targets indicate shared handling. In the incoming table, indices 119 and 120 both target `0x500f8` (the default/common branch), demonstrating why counting 180 entries as 180 distinct messages would be incorrect.

Selected verified mappings:

| index | incoming branch | outgoing branch |
|---:|---|---|
| 0 | `0x4cfbc` | `0x3f6d4` |
| 1 | `0x4c9d0` | `0x3f614` |
| 28 | `0x4f6bc` | `0x3fc44` |
| 127 | `0x43968` | `0x3e1cc` |
| 177 | `0x4fd34` | `0x3fd18` |
| 179 | `0x4fee0` | `0x3fda8` |

For index 127, incoming case `0x43968` calls receiver virtual slot 28 at `0x43b5c`; outgoing case `0x3e1cc` writes 16-bit literal `127` into the constructed message. The concrete GTF2 receiver vtable, payload semantics, and on-wire ID mapping are still unverified.

## Reproducibility

Run `python3 tools/fpk1/research/hmi/map_proxy_ipc.py proxy.dis OUTPUT_DIR` after disassembling the original proxy with `llvm-objdump -d --triple=armv7-unknown-linux-gnueabi`. It emits complete 180-row CSV inventories for incoming and outgoing tables. The optional `possible_receiver_virtual_slots_NOT_CFG_VERIFIED` field is a **heuristic**: it looks for nearby vtable-offset loads before `blx` in a linear instruction window bounded by the next case target. This is not a control-flow graph and must never be treated as a proven selector-to-callback map. In local extraction, 116 incoming case windows had at least one such candidate; outgoing windows had none with this heuristic.

## Replacement implementation contract

The next analysis should produce one semantic record per *distinct behavior* rather than per jump-table entry: `dispatch_index`, `input_payload_fields`, `validation`, `state_reads`, `state_writes`, `dp_ids`, `outgoing_messages`, `ui_state_effects`, `evidence_address`, `confidence`. Group aliases by branch target, then perform dataflow through the 141 distinct handlers. Do not substitute proxy callback-slot numbers for DP-IDs or claim Kanzi scene updates without following GTF2 handler logic. For an IAA replacement, the IPC adapter and state reducer should be kept separate from the renderer.
