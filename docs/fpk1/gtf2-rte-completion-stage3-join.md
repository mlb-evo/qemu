# ThreadMan RTEUpdateDone branch joins existing Stage3 startup path

Source: stock `STAGE2.1/bin/gtf2` (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`). This is an **integration/correction** to `gtf2-threadman-completion-events.md` and the already documented `gtf2-lifecycle.md` Stage3 chain, not a new Stage3 function discovery.

## Concrete RTE completion branch

`0x12dfb0` handles the internal event `eSIDThreadManRTEUpdateDone` (selector `0x2afa`). At `0x12e03c` it tests the per-run completion flag and, if unset, executes:

```asm
12e048 add r5,sp,#4
12e04c add r2,r4,#0xf8
12e050 add r1,r4,#8
12e054 mov r0,r5
12e058 bl  0x130510
12e05c mov r0,r5
12e060 bl  0x13076c
12e064 mov r0,r5
12e068 bl  0x13080c
12e06c mov r3,#1
12e070 strb r3,[r6]
```

These are **three calls on the same stack-local object**, not three independent RTE update handlers. `0x130510` initializes its fields (`+0,+4,+8,+0x18`, the last to -1) and installs an inner vtable pointer at `+8` via `0x1304ec`. `0x13080c` checks `+0x18`, optionally calls imported `0x10e2ac`, and restores the inner vtable at `+8`. It is cleanup/finalization-like; exact class identity unproven.

## Stage3 connection already present in lifecycle research

```asm
13076c push {r4,lr}
130774 bl 0x13067c
130778 cmp r0,#0
130784 bne 0x1307a8
130788 bl 0x13066c
13078c cmp r0,#0
130790 beq 0x1307d8
130794 bl 0x699594   ; GTF2 startEfsDriver()
130798 cmp r0,#0
13079c bne 0x1307b0
```

The direct `0x130794 → 0x699594` call was **already verified and documented** in `gtf2-lifecycle.md` as the delayed-HMI-start Stage3 path. The new join is the exact upstream event `eSIDThreadManRTEUpdateDone` through `0x12dfb0` and the local stack object. Therefore the correct synthesis is:

```
ThreadMan run() 0x12e380
  -> message loop 0x12e0a8
    -> processMessage 0x12dfb0
      -> eSIDThreadManRTEUpdateDone (0x2afa)
        -> 0x130510  construct temporary helper
        -> 0x13076c  conditionally run Stage3 startup path
          -> 0x13067c / 0x13066c guards
          -> 0x699594 startEfsDriver() [existing lifecycle finding]
        -> 0x13080c  finalize temporary helper
        -> mark RTE completion flag
```

## What this does not prove

- The event name does not prove that ASI RTE subscriptions have completed or identify the event producer.
- `0x13076c` does not always call `startEfsDriver()`: guard branches can bypass it.
- `0x130510` and `0x13080c` must not be described as independent IPC/RTE registration calls.
- The two ThreadMan completion flags and the separate Stage3 process-start return code should not be conflated.
- This does not supersede the other documented `startEfsDriver()` callsites `0x122eac` and `0x692f20`.

Next evidence target: producers of `0x2af9/0x2afa` and exact `0x13067c/0x13066c` DP predicates. Avoid duplicating existing `gtf2-lifecycle.md` analysis.
