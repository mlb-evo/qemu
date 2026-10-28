# GTF2 ThreadManager startup boundary: verified ARM call ordering

Original GTF2 SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This extends [entry/main investigation](gtf2-elf-entry-main-threadman.md) with a **new disassembly check**, and corrects the shorthand “`0x12e380` is the main event loop”: it is a startup/orchestration function, **not itself the receive loop**.

## Exact entry and arguments

Main `0x112e0c–0x112e18` passes **`sp+3192`** (stack object; `sp+3184+8`) as r0 to `0x12e380`, conditional on the non-error startup path. The three configuration bytes `[r5]`, `[r5+1]`, `[r5+2]` are read by the callee. Their option names/defaults require separate dataflow analysis.

## `0x12e380` execution order

| callsite | target | observed role / arguments |
|---|---|---|
| `0x12e3a8` | `0x12e294` | returns r0 into r4, subsequently used as manager object |
| `0x12e3b0` | `0x14c348` | initialization call, no explicit args set immediately beforehand |
| `0x12e3d8` | `0x12e124` | r0=manager; r1=config byte 1 |
| `0x12e3e8` | `0x12e0a8` | r0=manager; **synchronous receive/dispatch loop** |
| `0x12e3f4` | `0x12ddc8` | r0=manager; r1=config byte 0 |
| `0x12e424` | `0x12dd38` | r0=manager; r1=boolean derived from config bytes |
| `0x12e42c` | `0x12f6d8` | r0=[manager] |
| `0x12e430` | `0x12de3c` | return r0 saved as r6 |
| `0x12e460` | `0x69992c` | r0=[manager]; r1=return from 0x12de3c |
| `0x12e468` | `0x699f9c` | r0=[manager] |
| `0x12e474` | `0x12de74` | r0=manager; r1=config byte 1 |
| `0x12e478` | `0x68deb4` | no explicit args reset at callsite |
| `0x12e4ac` | virtual slot 4 | global object pointer loaded via `[0xab5618]`, then `[obj]` and `[vtable+0x10]` |
| `0x12e4bc` | virtual slot 17 | returned object, `[vtable+0x44]`, r1=1 |

**Critical control-flow consequence:** `0x12e0a8` is called **before** the later manager setup calls. It returns only when both loop exit flags are nonzero; therefore those later calls are **not necessarily executed during ordinary startup**. A linear call list is not a chronological startup timeline. This invalidates treating the entire `0x12e380` function as sequential initialization before entering steady state.

## `0x12e0a8`: actual message receive loop

- Initializes two stack exit flags to zero (`0x12e0b4–0x12e0bc`), preserving r0 as manager in r7.
- Loop header `0x12e104`: sets r0=3 and tests exit flags. While either flag is zero, branches to `0x12e0cc`.
- `0x12e0cc`: calls `0x69b29c` with r0=3, consistent with **message box channel 3 receive** already documented in the RTE-update path.
- `0x12e0d0–0x12e0d4`: if receive returns null, skip message dispatch and retry.
- On non-null: `0x14e58c` → `0x14e59c` prepare/extract message; `0x12dfb0` is called at `0x12e0f8` with r0=manager, r1=extracted message, r2/r3=addresses of the two exit flags. Then `0x14e914` cleanup, and repeat.
- The loop exits only when **both flags** are nonzero. Exact event selectors setting them and shutdown semantics need further inspection of `0x12dfb0`.

Thus the directly proven startup-to-event boundary is:

```
ELF entry -> constructors -> main(0x1126b8)
    -> manager factory 0x12e294
    -> 0x14c348
    -> configure manager 0x12e124
    -> RECEIVE LOOP 0x12e0a8
         -> channel 3 receive 0x69b29c
         -> extract event
         -> 0x12dfb0 event dispatcher
         -> cleanup and repeat
    -> post-loop teardown/other calls (semantics pending)
```

This explains why `eSIDThreadManRTEUpdateDone` arrives at `0x12dfb0` through channel 3 without needing a speculative IPC proxy mapping. **Next:** inspect `0x12dfb0` to enumerate both exit flags and early lifecycle event cases; identify `0x12e294` manager construction and `0x12e124` option semantics. Stage3 after the GTF2 launch request is out of scope.
