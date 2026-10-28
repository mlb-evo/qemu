# Proven producers of ThreadMan completion events and two missing startup DataPool writers

Original stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Reconciled with `gtf2-lifecycle.md` and `gtf2-ipc-to-dp.csv`: neither `0x02000236` nor `0x020002bb` appears in the 176-row CSV, which is a **restricted direct-writer inventory**, not a complete DataPool inventory.

## Completion message construction sites

A whole-executable scan for ARM MOVW immediates `0x2af9` and `0x2afa` found exactly these instruction addresses:

| Selector | MOVW instruction VA | Role |
|---|---|---|
| `0x2af9` | `0x114808` | Producer of `eSIDThreadManDPInitDone` |
| `0x2af9` | `0x12dfb0` | Consumer comparison |
| `0x2afa` | `0x693ff4` | Producer of `eSIDThreadManRTEUpdateDone` |
| `0x2afa` | `0x12dfd0` | Consumer comparison |

At `0x1147f8–0x114818`, the initialization routine invokes `0x69e2d4`, constructs the `0x2af9` message using `0x12ca9c`, then calls `0x12c994`. At `0x693ff0–0x694018`, a separate function constructs `0x2afa` through `0x12ca9c`, invokes `0x12c994`, then calls `0x12c9fc` for local cleanup. The latter helper calls `0x69b280` on the message's owned object. Both producers use the same message helper family; the consumer is `0x12dfb0` through `0x12e0a8`.

Do not equate `0x12c994` with confirmed queue insertion without following its callee `0x69b4ac` and the queue storage. Do not assume that `0x693ff0` has a direct BL caller: direct-BL census found **zero**. The function can be invoked via a vtable or callback pointer; that upstream edge remains to be resolved.

## Previously missed startup DP writer #1: 0x02000236

The original ELF contains two literal occurrences of `0x02000236`: `0x130688` (reader/guard) and `0x69436c` (writer). The latter is referenced by the function beginning at `0x694358`:

```asm
694358 ldr r3,[r1,#4]
69435c add r0,r0,#0x10
694360 ldr r1,[pc,#4]   ; [0x69436c] = 0x02000236
694364 ldrb r2,[r3,#3]  ; payload byte +3
694368 b 0x131390      ; DP setter, tail branch
```

The prior 176-DP inventory deliberately recognizes direct BL-to-setter patterns. This writer uses a **tail branch** and was therefore not represented in the CSV. The callback's source-level name is **not yet proven**; do not invent it from neighboring vtable entries.

## Previously missed startup DP writer #2: 0x020002bb

The original ELF contains two literal occurrences of `0x020002bb`: `0x130678` (reader/guard) and `0x693fec` (writer). Function `0x693fdc` writes a **fixed byte value** through a different DP helper:

```asm
693fdc add r0,r0,#0x10
693fe0 ldr r1,[pc,#4]  ; [0x693fec] = 0x020002bb
693fe4 mov r2,#171
693fe8 b 0x13143c
```

The fact that this DP is written to the value the Stage3 guard expects does **not** prove it has that value at the time of the guard read. Establish invocation order, conditional execution, and potential other writers before claiming that the Stage3 branch is always selected.

## Reconciled control-flow picture

```text
GTF2 initialization routine
  -> 0x114808 MOVW 0x2af9 -> 0x12ca9c -> 0x12c994
  -> ThreadMan processing loop 0x12e0a8
    -> 0x12dfb0 DPInitDone
      -> keyed-container operations and callback object setup

Separate GTF2 function 0x693ff0
  -> 0x693ff4 MOVW 0x2afa -> 0x12ca9c -> 0x12c994
  -> ThreadMan processing loop 0x12e0a8
    -> 0x12dfb0 RTEUpdateDone
      -> 0x13076c
        if DP 0x02000236 == 2: delayed HMI start
        else if DP 0x020002bb == 171: startEfsDriver()
        else: immediate HMI start
```

The source-level name of `0x693ff0`, its indirect callback/vtable registration, the transport between the producers and the queue consumer, and the real-time order of both messages are not yet established. This note records **binary-verified producer sites and DP writers**, not a complete IPC transport reconstruction.

## Reproduction

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x1147f8 --stop 0x11482c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x693fdc --stop 0x69401c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x694340 --stop 0x694370
```

Next: identify indirect pointer slot(s) to `0x693ff0` and `0x694358`; trace `0x69b4ac` and `0x69b29c` as the producer/consumer message bridge; then resolve callback names with direct vtable provenance.
