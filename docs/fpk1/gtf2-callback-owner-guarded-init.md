# Callback-table owner: upstream guarded initialization path

Source: original stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This note extends `gtf2-callback-object-vptr-and-caller.md` and integrates the previously documented separate HMI-owner, DP-slot and ViewManager lifecycles. Direct ARM BL targets and condition branches were decoded from executable bytes, not guessed from names.

## New direct caller

The only direct ARM `BL` caller of `0x68f594` found in the scanned executable interval `0x110000..0x700000` is **`0x12e014`**, inside a function beginning at **`0x12dfb8`**.

```asm
12dff4  mov r1, #2
12dff8  ldr r2, [pc, ...]
12dffc  bl 0x10e120
12e000  ldrb r3, [r5]
12e004  cmp r3, #0
12e008  bne 0x12e090         ; skip setup when flag already nonzero
12e00c  mov r0, r4
12e010  bl 0x12df20
12e014  bl 0x68f594         ; callback-table setup chain
12e018  mov r3, #1
12e01c  strb r3, [r5]       ; set initialized flag
12e020  b 0x12e090
```

Thus the previously documented `0x68f594 -> 0x68ee80 -> 0x69780c -> 0x6977a4` path is reached **conditionally** and followed by a byte flag set to one. The guard appears to prevent repeated setup *on this branch*. It does not by itself prove a process-wide singleton or a live IPC subscription. The enclosing routine has additional branches at `0x12e024` and `0x12e03c` that initialize a different subsystem when another flag is zero.

## Additional preceding configuration

The immediately preceding call `0x12df20` (at `0x12e010`) performs configuration before constructing the callback object:

```asm
12df50  bl 0x12dcd4
12df54  mov r1,#4
12df58  mov r2,#0
12df60  bl 0x12ff70
12df68  mov r1,#5
12df6c  mov r2,#0
12df70  bl 0x12ff70
12df78  mov r1,#3
12df7c  mov r2,#0x530
12df80  bl 0x12ff70
```

These are three direct calls with arguments `(4,0)`, `(5,0)`, `(3,0x530)` and the same object-derived first argument. **Do not call them ASI subscription parameters** without resolving `0x12ff70`.

## Updated architecture boundary

The newly traced path is:
```
0x12dfb8 (conditional init, flag check)
  -> 0x12df20 (pre-configuration)
  -> 0x68f594 (global storage initialization)
      -> 0x68ee80
          -> 0x69780c
              -> 0x6977a4 (52-byte object, vptr +0 = 0x88e6b8)
              -> 0x10eb7c (imported util::SharedPtrDefaultBase ctor)
  -> set initialized flag = 1
```

This is **separate from** HMI owner lazy singleton `0x2bae28/0x25ef60`, and separate from the GTF2-local 180-slot DP notification system `0x120e94/0x122338`. No edge between those mechanisms has been established yet.

## Next proof target

Identify callers of `0x12dfb8`, resolve the owner and address of its flag byte, and inspect what `0x12ff70` configures. Resolve ASI IPC registration via imports/callers rather than mistaking the shared-pointer constructor for registration. The 148 vtable entries are not confirmed wire-method indices.

No proprietary ELF bytes or implementation design is committed.
