# GTF2 DPInitDone producer located (ARM call chain)

Firmware: original Stage2.1 `bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Analysis of original code addresses, disassembled with llvm-objdump. **This closes the producer gap** left in `gtf2-dp-init-writebool.md`; the previous “no literal 0x2af9” observation is corrected: it is synthesized by ARM `movw`, not stored as a full 32-bit literal.

## Exact producer and enqueue

A direct scan of all GTF2 ARM disassembly finds `movw r2,#0x2af9` at **`0x114808`** (and dispatcher compare `movw r12,#0x2af9` at `0x12dfb0`). Producer lies inside function starting **`0x114650`**:

```asm
1147f4 mov  r0,#0
1147f8 mov  r1,#3
114800 bl   0x69e2d4       ; pre-event operation (exact purpose pending)
114804 mov  r1,#3
114808 movw r2,#0x2af9     ; eSIDThreadManDPInitDone
11480c mov  r0,r5          ; stack event wrapper, sp+440
114810 bl   0x12ca9c      ; creates channel-3 event with selector 0x2af9
114814 mov  r0,r5
114818 bl   0x12c994      ; sends event through wrapper
```

`0x12ca9c` passes `r0=3,r1=0x2af9` into **`0x69b6b8`**, stores returned message pointer and a non-null flag into the wrapper. `0x12c994` tests the flag, passes message pointer to **`0x69b4ac`** and updates its flag from the return. `0x69b4ac` reaches `0x68d060` via `0x68d7f8`/`0x68d570`. This is a real event construction/send chain, not a name-only guess. The exact lower transport semantics and send failure handling need further study.

**Direct caller:** `0x68c894` calls `0x114650`, from enclosing function **`0x68c860`**. `0x68c860` first calls `0x11511c`, then `0x68d56c` (stores result in global `0xdb085c`), and invokes `0x114650` with the result of `0x11511c`. It conditionally enters a later `0x11459c`/ `0x68d884` loop, then cleanup `0x1152c4`. Thus producer is in a substantial **initialization worker path**, not inside the receiver `0x12dfb0`.

## Cross-thread startup contract

```
producer path: 0x68c860 -> 0x114650 -> 0x69e2d4 -> construct(3,0x2af9) -> send
receiver path: 0x12e0a8 -> receive channel 3 -> 0x12dfb0
               -> 0x12df20 -> writeBool(DP 0x0200010e, config[2])
               -> 0x68f594 -> dp_done=1
```

The producer sends after `0x69e2d4` returns, which gives a **static intra-thread happens-before** edge. However, `0x69e2d4` is a loop that calls `0x69e1e4` and `0x751770`; it is not yet proven to be the complete DP initialization barrier or evidence that all DP subscriptions are ready. Similarly, no runtime timestamp or proof of successful send is implied.

## Remaining target

Trace how `0x68c860` is launched (thread creation/callback), determine what `0x69e2d4` does, and correlate `0x11511c` / `0x114650` initialization stages with actual DP readiness. This is the remaining upstream gap; do not investigate Stage3.
