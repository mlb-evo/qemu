# GTF2 channel-0: concrete virtual handlers and GUI datapool message names

Evidence: original ARM32 `gtf2` binary, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`; vtable words read from ELF file at virtual address minus `0x100000`. Follows `gtf2-hmi-channel0-handler-map.md`.

## Important correction: factories are lazy static singletons

Factories `0x12c5c0`, `0x12c11c`, `0x12b5dc`, `0x12c694`, `0x12c4f0`, `0x12c270`, `0x12b6b8` each test a guard word and return the same fixed global object address on every call. In particular, selectors **5, 6, 7, 8 all reference the SAME handler object** returned by `0x12c694` (global `0xab5e50`), not distinct instances. Earlier note about separate instances was incorrect.

## Verified vtable first slots

| Selector(s) | vtable VA | first virtual handler | role |
|---|---|---|---|
| 2 | `0x7c2d10` | `0x12c5bc` | immediate `bx lr` (no-op) |
| 3 | `0x7c2ba8` | `0x12c168` | parses message fields via `0x69b4a0` |
| 4 | `0x7c2900` | `0x12b628` | parses field via `0x69b494` and calls `0x6ab564` |
| 5,6,7,8 | `0x7c2d20` | `0x12c6e0` | shared switch on actual message selector |
| 10 | `0x7c2c78` | `0x12c53c` | parses message field via `0x69b494` |
| 11 | `0x7c2bf8` | `0x12c2bc` | parses fields via `0x69b488` / `0x69b4a0` |
| 12 | `0x7c2910` | `0x12b704` | parses field via `0x69b4a0` |

The vtable first slot for selector 2 points to `0x12c5bc` (not the adjacent `0x12c630`).

## Identified GUI datapool event names: selectors 5..8

The shared handler `0x12c6e0` calls `0x69b45c(message)`, subtracts 5, checks <=3 and dispatches via ARM PC jump table `0x12c70c–0x12c718`:

| selector | target | literal string VA | string in binary |
|---|---|---|---|
| 5 | `0x12c740` | `0x7c2a59` | `eSIDGuiDpStatus` |
| 6 | `0x12c76c` | `0x7c2a69` | `eSIDGuiDpVariantLanguageChange` |
| 7 | `0x12c71c` | `0x7c2a88` | `eSIDGuiDpNotification` |
| 8 | `0x12c7a0` | `0x7c2a9e` | `eSIDGuiDpBatchNotification` |

All four call `0x69b19c` with message/event diagnostics (including common literal at `0x7c289c`: `eTRCL_HMI::eTRCO_EVENT::eTROR_NONE debug: `). Selector 7 additionally writes result code 11 to the temporary result structure and clears a halfword at offset 4. Selector 8 tail-branches to `0x12c630` after logging, which enumerates entries obtained from `0x6a5184` and emits `0x6aa204` per entry; other cases return after logging.

**Scope:** these are verified channel-0 *message names*, not yet mapped to specific DP-ID or scene-property writes. The logging strings are corroborated by each switch arm, not merely guessed from string proximity.

## Next

Trace `0x12c630` -> `0x6a5184` -> `0x6aa204` to reconstruct batch datapool notifications, and trace producers of `eSIDGuiDpStatus` and `eSIDGuiDpNotification`. Determine remaining handlers' semantic names via field parsing and cross-references. No Stage3.
