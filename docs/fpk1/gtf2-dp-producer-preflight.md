# GTF2 DPInitDone producer: fixed eight-slot preflight and worker registration

Source: original Stage2.1 `bin/gtf2` SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`; checked against local `gtf2-all.dis` and ELF bytes. This adds to `gtf2-dp-init-producer.md`.

## `0x69e2d4` before event send

`0x1147f4–0x114800` calls `0x69e2d4(0,3)`; only **after it returns** does `0x114808` construct `0x2af9`.

`0x69e2d4` invokes `0x69b19c` first, then loops index `r4` from **0 through 7**, calling `0x69e1e4(index, r6=0, r5=3)` on each iteration. The bound is established by `0x751770`, which is literally:
```asm
751770 mov r0,#8
751774 bx lr
```
`0x69e1e4` reads a global initialization byte, lazily calls `0x69e0e0` if zero, checks index against eight, then calls `0x751d04(index,3)` and `0x751ce8(index,0)`; compares/stores 16-bit cached state arrays, invokes change hooks `0x751800`, `0x751998`, `0x751b4c`, `0x751cd4`, then tail-calls `0x6a071c(index)` when state changes. Thus this is a **bounded per-slot state update across eight entries**, not an arbitrary wait or a known IPC readiness probe. No blocking wait or retry of DPInitDone is visible in this loop.

The exact meaning of eight slots and parameter 3 remains unknown; avoid naming them DP subscriptions without proof.

## Producer worker linkage: indirect function pointer, not direct BL

There is no ARM direct `BL 0x68c860` in the full disassembly. The function pointer `0x68c860` is stored at literal/data VA **`0x130498`** within a nearby descriptor table. The same table includes `0x68c900` at `0x13048c`, `0x68c84c` at `0x130494`, `0x68c9b0` at `0x1304a0`, and `0x68c9c4` at `0x1304a4`. At `0x130454–0x130464`, a setup function calls `0x13019c` with a descriptor pointer and additional arguments; this is a **plausible registration route** for `0x68c860` but not yet proven that the exact descriptor is the one selected at runtime. Do not claim a new thread is launched merely because a code pointer appears in a table.

`0x68c860` performs `0x11511c` to obtain a context pointer, stores the return of `0x68d56c` in global `0xdb085c`, then invokes `0x114650(context)` and may enter `0x11459c` / `0x68d884` processing loop. It cleans up via `0x1152c4`.

## Refined behavior boundary

```
worker entry 0x68c860 (indirectly referenced)
  -> context acquisition 0x11511c
  -> 0x114650(context)
     -> create/register local handler objects (several 0x12bfcc calls)
     -> 0x69e2d4(0,3)
        -> for i=0..7: 0x69e1e4(i,0,3)
     -> enqueue event 0x2af9 on channel 3
receiver 0x12e0a8 -> 0x12dfb0
  -> writeBool(0x0200010e, config[2])
  -> DP completion hooks -> dp_done=1
```

This **proves the immediate prerequisite** for enqueueing DPInitDone: an eight-slot state-update pass must return. It does **not** prove that every DP is initialized, nor that the enqueue succeeds, nor that an external service is ready.

## Next

Trace `0x13019c` descriptor registration and its callback invocation to prove the worker launch. Classify `0x751d04`, `0x751ce8`, `0x6a071c` to name the eight slots. Inspect return/exception paths in `0x114650` to determine whether a failure can skip the event.
