# RTEUpdateDone producer is slot 136 of the already-recovered IHmiKss callback table

Verified against the original stock `STAGE2.1/bin/gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This resolves the indirect entry of `0x693ff0` left open in `gtf2-threadman-producers-and-startup-dp-writers.md`. The table itself and callback object construction were already established in `gtf2-callback-object-vptr-and-caller.md`; **do not count them as new discoveries**.

## Exact indirect function pointers

Scanning the entire original ELF for little-endian absolute pointers to the two functions finds one occurrence each:

| Table base | Slot index (zero-based) | Pointer slot VA | Target | Meaning |
|---|---:|---|---|---|
| `0x88e6b8` | **96** | `0x88e838` | `0x694358` | `payload[3]` to DP `0x02000236` via tail branch `0x131390` |
| `0x88e6b8` | **136** | `0x88e8d8` | `0x693ff0` | create `eSIDThreadManRTEUpdateDone` (selector `0x2afa`) |
| `0x88e6b8` | **137** | `0x88e8dc` | `0x693fdc` | write constant `171` to DP `0x020002bb` via tail branch `0x13143c` |

These are entries in the **same 148-entry callback pointer table** already associated with the 52-byte object constructed by `0x6977a4`. The pointer to `0x693ff0` is not a direct `BL` callsite; therefore the earlier zero-direct-call observation is fully explained by indirect dispatch. The exact external ASI method index / IPC method name for slot 136 is **not yet proven**. Slot adjacency to the DP writer at index 137 does not prove those two callbacks execute consecutively.

The 148-entry table ends at index 147 (`0x88e904 -> 0x694024`). Following words at `0x88e908` are **not** further entries of this same table; they begin a separate data/vtable region.

## Machine code at the producer

```asm
693ff0 push {r0,r1,r4,lr}
693ff4 movw r2,#0x2afa
693ff8 mov r1,#3
693ffc mov r0,sp
694000 bl 0x12ca9c
694004 mov r0,sp
694008 bl 0x12c994
69400c mov r0,sp
694014 bl 0x12c9fc
694018 pop {r2,r3,r4,pc}
```

`0x12c994` checks the local wrapper's byte `+4` and calls `0x69b4ac` on its pointer `+0`; `0x69b4ac` uses GTF2 IPC/message transport helpers `0x68d7f8`, `0x68d570`, `0x68d060` and checks a `-1` failure result. The consumer `0x69b29c` calls `0x68d7f8`, `0x68d570`, `0x6abf20`, then `0x68cd70` / `0x68ce1c` / `0x68cf00` to receive a message into an object buffer at `+0x10`. This strengthens the message transport link but does not establish the concrete transport endpoint or serialization contract.

## Reconciled application-level chain

```text
IHmiKss callback object [vptr 0x88e6b8]
  + slot 136 -> 0x693ff0
      -> construct 0x2afa message
      -> 0x12c994 -> 0x69b4ac (send-like IPC transport)
ThreadMan run 0x12e380
  -> 0x12e0a8 -> 0x69b29c (receive-like IPC transport)
      -> 0x12dfb0 (processMessage)
          -> eSIDThreadManRTEUpdateDone
          -> 0x130510 / 0x13076c / 0x13080c
          -> conditional HMI startup / Stage3 path
```

**Important distinction:** A callback table pointer is evidence of a registered callable implementation, not proof of the external method number, registration timing, or a specific runtime callback invocation. Recover those by tracing the interface descriptor and dispatch registration rather than assigning a name based solely on index.

## Reproduction

```python
import struct
blob = open('gtf2', 'rb').read()
for target in (0x693ff0, 0x694358, 0x693fdc):
    needle = struct.pack('<I', target)
    matches = []
    off = 0
    while (off := blob.find(needle, off)) >= 0:
        matches.append(hex(off + 0x100000))
        off += 1
    print(hex(target), matches)
```

Original executable LOAD has VA base `0x100000` and file offset zero for these pointer slots. This scan yields `0x88e8d8`, `0x88e838`, `0x88e8dc` respectively.

Next: trace the method descriptor corresponding to slot 136, and inspect `0x68d060`/`0x68cf00` transport operations without assuming that callback slot indices equal ASI IPC method IDs.
