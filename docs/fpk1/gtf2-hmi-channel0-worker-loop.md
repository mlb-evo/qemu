# GTF2 HMI worker: channel 0 message loop and corrected barrier flag wiring

Source: original Stage2.1 `bin/gtf2` ARM32, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Direct inspection of `gtf2-all.dis` on 2026-10-28. This corrects the earlier assumption that the main thread's two-event barrier is itself the steady-state HMI loop.

## HMI worker `0x68c860`

At `0x68c894` it invokes initialization `0x114650(context)`; if return is zero, it branches directly to cleanup `0x68c8d4`. Otherwise it clears global stop byte `0xdb0858` at `0x68c8ac` and loops:

- `0x68c8b0`: read stop byte; nonzero exits to cleanup.
- `0x68c8c0`: call `0x11459c(context)`; save return in r6.
- `0x68c8c8`: call `0x68d884()`.
- `0x68c8cc`: if `0x11459c` returned nonzero, repeat; otherwise cleanup.
- `0x68c8d4`: `0x1152c4`, object cleanup and return 0.

**Therefore HMI processing is a separate worker loop, not the tail of `0x12e380`.** Its continuation requires BOTH stop byte zero and a nonzero return from `0x11459c`.

## One iteration `0x11459c`: actual receive channel

- `0x1145a4` obtains manager singleton `0x12e294`; `0x1145a8` calls `0x12dccc`.
- `0x1145cc`: `0x699a60` called with state 1.
- `0x1145d0`: sets r0=**0**; `0x1145d4` calls `0x69b29c`, i.e. **receives from internal channel 0**, NOT the channel-3 startup event barrier.
- `0x1145f4`: `0x699a60` with state 2; `0x1145f8` and `0x1145fc` run helper calls.
- If message pointer nonnull (`0x114600`), `0x114618` calls `0x12c008(context+27312, context, message)`, `0x114620` releases the message via `0x69b280`, and `0x114628` calls `0x6a9f74(context)`.
- `0x114644`: `0x699a60` with state 3; `0x114648`: **unconditionally returns 1**.

**Critical consequence:** the worker does not stop due to a zero return from `0x11459c` on its ordinary code path; its effective normal exit gate is the stop byte `0xdb0858`. The message receive may block; no guarantee that changing the byte wakes it without a message or transport cancellation.

## Startup barrier corrected pointer mapping

In `0x12e0a8`, stack bytes are initialized at `[sp+6]` and `[sp+7]`. `0x12e0e8` passes `r2=sp+7`, and `0x12e0ec` passes `r3=sp+6` to `0x12dfb0`. Therefore:

- `DPInitDone` `0x2af9` sets **`[sp+7]`** (r2), at `0x12e01c`.
- `RTEUpdateDone` `0x2afa` sets **`[sp+6]`** (r3), at `0x12e070`.
- `0x12e104` checks `[sp+7]` then `[sp+6]`; exits only when both are set.

This reverses the stack-offset labels previously written in `gtf2-threadman-init-barrier.md`, without changing the two-event AND condition.

## Lifecycle interpretation

`0x12e124` starts DP and HMI workers; main thread then blocks on channel 3 for the two completion events. HMI worker independently receives channel-0 messages, and its callback `0x68c84c` writes the stop byte. Main thread subsequently performs shutdown after its two-event wait. The reason that both completion events lead to this shutdown path is **still a real unresolved architectural question**; static disassembly verifies the control flow but does not justify labeling the barrier as a normal steady-state readiness signal. Check the source and scheduling of `RTEUpdateDone`, and whether `0x12e380` is intentionally a finite supervisor. Do not assume the HMI worker is stopped before the second event arrives.

## Next

Trace `0x12c008` dispatch and `0x6a9f74` state transitions, then identify producer of channel-0 messages and whether shutdown is intended on both startup events. No Stage3 analysis.
