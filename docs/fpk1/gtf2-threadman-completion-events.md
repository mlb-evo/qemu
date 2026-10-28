# Thread-manager event names resolve callback initialization trigger

Stock `STAGE2.1/bin/gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Cross-checked against the complete 3420-line `gtf2-lifecycle.md`; these exact addresses are not already covered there. This note corrects the tentative selector interpretation in `gtf2-guarded-init-real-entry-and-caller.md`.

## Verified source-level names, not guessed transport IDs

The dispatch function **0x12dfb0** compares `r1` against `0x2af9` and `0x2afa` at `0x12dfb4` and `0x12dfd8`. Its own ARM literal loads for the two diagnostic calls identify them:

| Value | Diagnostic string VA | Exact string | Conditional action |
| --- | --- | --- | --- |
| `0x2af9` | `0x7c33d5` | `processMessage(eSIDThreadManDPInitDone)` | check flag at `r2`; `0x12df20`, `0x68f594`, set flag |
| `0x2afa` | `0x7c33fd` | `processMessage(eSIDThreadManRTEUpdateDone)` | check flag at `r3`; `0x130510`, `0x13076c`, `0x13080c`, set flag |
| other | `0x7c3428` | `processMessage(): Unexpected Message` | unexpected-message diagnostic |

Literal slots `0x12e09c`, `0x12e0a0`, `0x12e0a4` point to these strings respectively. The names are embedded diagnostics and indicate **internal ThreadMan completion events**, not external IPC method IDs. A call to `0x68f594` follows the **DPInitDone** branch, not the RTEUpdateDone branch. This does not prove what `0x68f594` registers with any external service.

## Direct upstream call chain

A complete direct ARM BL scan of the original executable PT_LOAD found:

- `0x112e18 BL 0x12e380` (one direct caller)
- `0x12e3e8 BL 0x12e0a8` (one direct caller)
- `0x12e0f8 BL 0x12dfb0` (one direct caller)

The routine `0x12e380` has its own literal diagnostic `run()` at `0x7c34bf` (literal slot `0x12e4c8`). It first calls `0x12e294`, then `0x14c348`, `0x12e124`, and the `0x12e0a8` processing loop.

At `0x12e0a8`, `0x69b29c` supplies a nonnull object, `0x14e58c` stores it in a stack-local pointer, and `0x14e59c` (a wrapper that loads the pointer and tail-branches to `0x69b45c`) produces the value passed as `r1` to `0x12dfb0`. The two byte addresses passed as `r2/r3` are local flags at `sp+7` and `sp+6`. The loop repeats until both are nonzero (`0x12e104..0x12e11c`). This proves a **two-event completion wait/dispatch** structure. Exact origin of the queue messages remains open.

The higher-level caller `0x112e18` sits in the GTF2 initialization path and passes a stack object to `run()`. Its nearby ELF diagnostic string `Starting initialization` at `0x7bd731` is referenced by the surrounding routine, but do not claim it is emitted at a particular runtime timestamp without a trace.

## Corrected interpretation

The previously observed keyed-container operations `0x12df20 -> 0x12ff70` are executed on the DP-init-complete path, followed by creation of the 52-byte callback object. The event name provides the first reliable semantic classification of the trigger; it does **not** make `0x12ff70` an IPC configuration function. `0x10eb7c` remains the already-resolved `util::SharedPtrDefaultBase` constructor.

New known chain:
```
0x112e18
  -> 0x12e380 ('run()')
    -> 0x12e0a8 (process two completion events)
      -> 0x12dfb0 ('processMessage')
        eSIDThreadManDPInitDone (0x2af9)
          -> 0x12df20 (keyed-container operations)
          -> 0x68f594 -> 0x68ee80 -> 0x69780c -> 0x6977a4
        eSIDThreadManRTEUpdateDone (0x2afa)
          -> 0x130510 -> 0x13076c -> 0x13080c
```

Next: inspect the producers of both named completion messages and the side effects of the three RTEUpdateDone calls. Distinguish *ThreadMan completion* from actual ASI IPC subscription. No implementation specification or firmware bytes committed.
