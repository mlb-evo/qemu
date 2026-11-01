# GTF2 DP-init barrier: newly verified side effects and post-barrier ordering

Source original `STAGE2.1/bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. ARM instructions checked directly using `llvm-objdump -d --triple=armv7-unknown-linux-gnueabi` over a synthetic section header; no binary bytes changed. This extends [two-event barrier](gtf2-threadman-init-barrier.md) rather than repeating it.

## DPInitDone exact path

`0x12dfb0` dispatches `0x2af9`:
```
0x12e000  test dp_done
0x12e00c  r0 = manager
0x12e010  BL 0x12df20
0x12e014  BL 0x68f594
0x12e018  mov r3,1
0x12e01c  strb r3,[r5]   ; dp_done=1
```
**Correction to earlier wording:** `0x68f594` is invoked by **the dispatcher** at `0x12e014`, not by `0x12df20` internally. The side effects occur **before** the DP completion flag is set.

### `0x12df20` is not merely a notification

- `0x12df50` calls `0x12dcd4(manager)`.
- `0x12df60` calls `0x12ff70(manager+376, 4, 0)`.
- `0x12df70` calls `0x12ff70(manager+376, 5, 0)`.
- `0x12df80` calls `0x12ff70(manager+376, 3, 0x7530)`.

At `0x12dcd4`, the manager byte at **`manager+0x18c`** (396) is read, then passed to `0x131534` with a literal **`0x0200010e`** at `0x12dd34`:
```
0x12dd10  ldrb r2,[r4,#0x18c]
0x12dd14  add r0,sp,#4
0x12dd18  ldr r1,[pc,#0x14]  ; literal 0x0200010e
0x12dd1c  bl 0x131534
```
This is a **new concrete DP-ID connection**: `DPInitDone` → manager flag `+0x18c` → helper `0x131534` with DP-ID `0x0200010e`. The exact semantics of `0x131534` (setter, notifier, registration) remain to be established. `manager+0x18c` is populated in `0x12e3dc–0x12e3e4` from configuration byte 2, **before** the receive barrier.

### `0x68f594` side effects

```
0x68f594  push {r4,lr}
0x68f598  load literal 0xab5628
0x68f59c  mov r0,#4
0x68f5a0  BL 0x10e384
0x68f5a8  BL 0x68ecf0
0x68f5b4  store return from 0x10e384 into global 0xdb0c9c
0x68f5b8  BL 0x68ee80
0x68f5bc  BL 0x12e294   ; manager singleton/factory
0x68f5c0  add r0,r0,#344
0x68f5c8  B 0x769a6c   ; tail call
```
The literal `0xab5628` is passed as an argument to `0x10e384`; **do not call it a class name without symbol evidence**. This creates/stores a global object and associates work with manager subobject `+344` via `0x769a6c`. Exact object type and whether `0x769a6c` subscribes or starts work are not yet verified.

## Post-barrier calls are reachable only after both completion flags

`0x12e380` calls `0x12e0a8` at `0x12e3e8`. On return:
1. `0x12e3f4`: `0x12ddc8(manager, config[0])`
2. `0x12e424`: `0x12dd38(manager, derived_boolean)`
3. `0x12e42c`: `0x12f6d8([manager])`
4. `0x12e430`: `0x12de3c()` then `0x12e460`: `0x69992c([manager], result)`
5. `0x12e468`: `0x699f9c([manager])`
6. `0x12e474`: `0x12de74(manager, config[1])`
7. `0x12e478`: `0x68deb4()`
8. `0x12e4ac`: virtual call via global `0xab5618` vtable offset `0x10`; `0x12e4bc`: virtual call at offset `0x44` with argument 1.

**New finding:** `0x12de74` calls `0x12fdb4` with ordered internal IDs **3,4,5,2,1**, and optionally ID **0** if config[1] is true. `0x12fdb4` walks a keyed tree by comparing `[node+4]` with the requested ID; it is **not a proven timer or DP write**. These IDs must not be conflated with DP-ID `0x0200010e`.

## Producer still unproven

The direct receiver and its side effects are verified. The actual producer(s) of `eSIDThreadManDPInitDone` `0x2af9`, and the precondition for enqueueing it onto channel 3, have **not** been proven. Avoid treating an event diagnostic string as evidence of producer identity.

## Next targeted analysis

1. Follow `0x131534` to prove the operation on DP-ID `0x0200010e`.
2. Follow `0x769a6c` and `0x68ee80` to identify the object initialized on DPInitDone.
3. Identify the exact sender of `0x2af9` by tracing channel-3 send callsites and event object construction, not by repeating the 180-case proxy table.
4. Classify post-barrier calls as launch, subscription, rendering, or service activation with evidence.
