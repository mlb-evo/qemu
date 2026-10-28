# Reassessment of guarded callback initialization: 0x12ff70 is not a proven IPC configurator

Source: stock extracted `gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This corrects the tentative wording in `gtf2-callback-owner-guarded-init.md` after inspecting the callee, not just its arguments.

## Actual function body

```asm
12ff70 ldr r0,[r0]
12ff74 cmp r0,#0
12ff78 bxeq lr
12ff7c ldr r3,[r0,#4]
12ff80 cmp r1,r3
12ff84 bge 12ff98
12ff88 ldr r0,[r0,#0x48]
12ff8c cmp r0,#0
12ff90 bne 12ff7c
12ff94 bx lr
12ff98 cmp r3,r1
12ff9c bge 12ffb0
12ffa0 ldr r0,[r0,#0x4c]
12ffa4 cmp r0,#0
12ffa8 bne 12ff7c
12ffac bx lr
12ffb0 cmp r0,#0
12ffb4 bxeq lr
12ffb8 cmp r2,#0
12ffbc add r0,r0,#8
12ffc0 bne 12ffc8
12ffc4 b 12fec8
12ffc8 mov r1,r2
12ffcc b 12fc64
```

The routine traverses a structure using `+0x48`/`+0x4c` pointers according to a comparison with the integer key at `+0x04`, then tail-calls `0x12fec8` or `0x12fc64` on a field at node `+8`. This is a **keyed tree/container lookup/update pattern**, not a demonstrated wait or IPC configuration API. The precise effects of the two tail targets remain to be established.

The preceding `0x12df20` passes keys `4,5,3` and values `0,0,0x530` respectively to this routine. Those are **container operations**, not established ASI method IDs or transport channels. In particular, `0x530` must not be promoted to an IPC channel identifier from this call alone.

## Upstream linkage limitation

A direct ARM BL scan of `0x110000..0x780000` finds **zero direct BL callers of `0x12dfb8`**. A literal 32-bit address search of the extracted ELF also finds no exact pointer to `0x12dfb8`. This is negative evidence limited to those two mechanisms; the function may be reached by a computed branch, a veneer, a register-indirect call, or other paths. No invocation count or initialization timing can be asserted.

The existing chain from `0x12e014` through `0x68f594`, `0x68ee80`, `0x69780c`, and `0x6977a4` is still valid *conditional on execution of the `0x12dfb8` branch*. `0x10eb7c` is already resolved to `util::SharedPtrDefaultBase` constructor and is not the IPC subscription.

## Integration with prior GTF2 findings

The large `gtf2-lifecycle.md` already proves a separate 180-slot DP event accumulator and a ViewManager-owned event queue. The container traversed by `0x12ff70` is **not proven identical** to either subsystem. The HMI owner singleton and the 52-byte callback-vtable object are also separate observations pending a real dataflow join.

Next inspect `0x12fec8` and `0x12fc64` to classify the container's value semantics; then trace the `0x12dfb8` entry via its actual calling convention. Avoid further 'IPC configuration' claims until ASI import or descriptor/registration code is directly linked.
