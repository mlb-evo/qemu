# GTF2 channel-0 HMI handler registration map (original ARM)

Original `STAGE2.1/bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Directly inspected local original disassembly `/mnt/data/gtf2-all.dis`. This extends `gtf2-hmi-channel0-dispatch.md` with a **verified factory-to-selector table**, not guessed handler names.

## Direct registration sites in `0x114650`

`r5 = HMI context + 27312` (at `0x114668–0x114674`). Each constructor returns an object in r0, moved to r2, with r1 set to the selector and r0 set to r5; `0x12bfcc` installs the pointer. Entries:

| selector | object factory | registration BL | comment |
|---:|---|---|---|
| 2 | `0x12c5c0` | `0x1146e4` | distinct constructor |
| 3 | `0x12c11c` | `0x1146f8` | distinct constructor |
| 4 | `0x12b5dc` | `0x11470c` | distinct constructor |
| 5 | `0x12c694` | `0x114748` | shared factory |
| 6 | `0x12c694` | `0x11475c` | shared factory |
| 7 | `0x12c694` | `0x114734` | shared factory |
| 8 | `0x12c694` | `0x114720` | shared factory |
| 10 | `0x12c4f0` | `0x114784` | distinct constructor |
| 11 | `0x12c270` | `0x114770` | distinct constructor |
| 12 | `0x12b6b8` | `0x114798` | distinct constructor |

**Not registered by this block:** selectors 1, 9, 13. This does not prove those slots remain empty after other registrations or that they cannot receive events.

## Important indexing detail

`0x12bfcc` accepts only selector IDs **2 through 13**: it calculates unsigned 16-bit `id-2`, checks `<=11`, then writes `table[id]`. So `1` is **not a valid registration through this helper**, even though dispatcher `0x12c008` indexes `table[1]` for selector 1. The dispatcher accepts selectors 1..13 by unsigned 16-bit `selector-1 <= 12`, loading `table[selector]`; all others use `table[14]` as fallback. This mismatch is intentional in code, not evidence that selector 1 has a handler.

Four selector IDs (5,6,7,8) are built by the same factory `0x12c694`, but separate instances are returned by separate calls. Do not assume they share state or callback identity without inspecting factory internals.

## Downstream dispatch contract

`0x11459c` receives channel-0 message -> `0x12c008` obtains selector via `0x69b45c` -> looks up handler -> `BLX [vtable+0]` -> `0x6aa3ac` post-dispatch, optionally `0x6aa204` if temporary flag set. These selector IDs are **not** external IPC IDs, DP-IDs, or thread registry IDs.

## Next work

For each factory, identify actual vtable pointer and first virtual method, then trace effects on HMI state, DP-ID and scene properties. Determine whether slots 1/9/13 and fallback 14 are populated by other initialization paths. No Stage3.
