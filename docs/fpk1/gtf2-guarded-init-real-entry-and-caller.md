# Correction: real entry of guarded initialization is 0x12dfb0, called directly

Source: original stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

## Corrected function boundary

The previous `gtf2-callback-guard-container-correction.md` reported zero direct callers of `0x12dfb8`. That was an overly literal prologue-based scan. **The entry is `0x12dfb0`, with two instructions before the PUSH prologue**:

```asm
12dfb0  movw r12,#0x2af9
12dfb4  cmp  r1,r12
12dfb8  push {r4,r5,r6,lr}
12dfbc  mov r4,r0
12dfc0  sub sp,sp,#0x20
12dfc4  mov r5,r2
12dfc8  mov r6,r3
12dfcc  beq 12dfe4
12dfd0  movw r3,#0x2afa
12dfd4  ldr r0,[pc,#0xbc]
12dfd8  cmp r1,r3
12dfdc  bne 12e078
12dfe0  b 12e024
```

The direct caller is at **`0x12e0f8 BL 0x12dfb0`**, in function beginning `0x12e0a8`:

```asm
12e0cc bl 0x69b29c
12e0d0 subs r1,r0,#0
12e0d4 beq 12e104
12e0d8 mov r0,sp
12e0dc bl 0x14e58c
12e0e0 mov r0,sp
12e0e4 bl 0x14e59c
12e0e8 mov r2,r6
12e0ec mov r3,r5
12e0f0 mov r1,r0
12e0f4 mov r0,r7
12e0f8 bl 0x12dfb0
12e0fc mov r0,sp
12e100 bl 0x14e914
```

The callee first compares the input `r1` to **`0x2af9`** and **`0x2afa`**, then branches to two distinct initialization paths. Therefore the callback object is created only on the relevant gated branch, not unconditionally for every invocation. `0x12e0a8` also loops around `0x69b29c` until its two stack-local status bytes become nonzero; the precise semantics of these helper functions are not yet established.

**Correction to previous research:** lack of BL references to `0x12dfb8` does not mean the function is only indirectly invoked. Searching for a canonical ARM prologue alone can miss a real function entry with pre-prologue comparisons. The documented zero-caller observation is true only for the *interior address* `0x12dfb8`, not for the function.

## 0x12ff70 container semantics

The full body of `0x12ff70` was checked against original bytes. It follows keyed tree links `node+0x48` and `node+0x4c` comparing `node+4` to `r1`, then dispatches from `node+8` to `0x12fec8` when `r2=0`, or `0x12fc64` when `r2!=0`. These are not identified ASI IPC setup calls. The `0x12fec8` path includes `0x12fe04`, version/check comparisons, and a tail call to imported `0x10e264`; `0x12fc64` invokes `0x127f48`, imported `0x10eb10`/`0x10f1dc`, then `0x113f24`. Exact semantics of those imported routines require relocation lookup.

## Confirmed joined path

```
0x12e0a8 (loop, obtain/transform input via 0x69b29c, 0x14e58c, 0x14e59c)
  -> BL 0x12dfb0 (key selector 0x2af9 or 0x2afa)
     -> conditional 0x12df20 (keyed container updates)
     -> conditional 0x68f594
        -> 0x68ee80 -> 0x69780c -> 0x6977a4
           (52-byte callback object with vptr 0x88e6b8)
        -> 0x10eb7c (imported util::SharedPtrDefaultBase constructor)
```

This is **not** proof that `0x2af9`/`0x2afa` are IPC method numbers. Their role is observed as selectors in the function, but transport provenance must be established by tracing `0x14e59c` and `0x69b29c`.

This corrects the previous prologue boundary and caller-negative conclusion. Do not create an IAA implementation contract from this evidence.
