# GTF2 ThreadManager two-event initialization barrier

Original `STAGE2.1/bin/gtf2` SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This document corrects the earlier description of the two `0x12e0a8` flags as shutdown flags: they are **initialization-completion flags**. All offsets below are original ARM ELF VAs.

## Dispatch `0x12dfb0` (verified ARM branch comparisons)

| event selector | diagnostic string at original VA | action | flag |
|---|---|---|---|
| `0x2af9` | `0x7c33d5`: `processMessage(eSIDThreadManDPInitDone)` | `0x12df20`, then `0x68f594`; sets `*r2=1` | flag A at loop stack `sp+6` |
| `0x2afa` | `0x7c33fd`: `processMessage(eSIDThreadManRTEUpdateDone)` | `0x130510` → `0x13076c` → `0x13080c`; sets `*r3=1` | flag B at loop stack `sp+7` |
| other | `0x7c3428`: `processMessage(): Unexpected Message` | diagnostic only | none |

The event value is passed as r1 to `0x12dfb0` from `0x14e59c` and compared at `0x12dfb4` / `0x12dfd8`. Both branches skip their work if the corresponding flag is already set (`0x12e000` and `0x12e03c`), so each action runs **at most once per invocation of the wait loop**. This does not establish whether the events are delivered once globally.

## Exact barrier semantics

At `0x12e0a8`, the caller initializes two stack bytes to zero. On every iteration `0x12e104` checks flag B first, then flag A. If **either** is zero, it receives the next message on internal channel 3 via `0x69b29c`. Only when **both** are nonzero does it return to `0x12e380` at `0x12e3ec`. The two event arrival orders are accepted. The names `DPInitDone` and `RTEUpdateDone` come from the original diagnostic strings; the producer's exact readiness criteria still require proof.

## DP-init branch and timer configuration

`0x12df20` performs `0x12dcd4`, then calls `0x12ff70` three times with `this+376`:
- ID **4**, argument **0** at `0x12df60`;
- ID **5**, argument **0** at `0x12df70`;
- ID **3**, argument **0x7530 = 30000** at `0x12df80`.

These are **internal helper IDs and arguments**, not DP-IDs or established milliseconds; `0x12ff70` semantics are not yet verified. The dispatcher then invokes `0x68f594` before setting flag A. This branch is a concrete DP initialization completion action but **does not yet prove all datapool subscriptions are active**.

## RTE-update branch

When flag B is clear, `0x12e048–0x12e068` constructs a temporary object from `manager+8` and `manager+248`, calls guarded HMI/Stage3 startup helper `0x13076c`, destroys the temporary, and sets flag B. Previous research already linked `0x130794` conditionally to `startEfsDriver()`. Do not equate receipt of RTE update with successful Stage3 launch.

## Manager construction before the barrier

`0x12e1a8` (called by factory `0x12e294`, pending full caller verification) allocates **580 bytes** at `0x12e1b4`; initializes fields at `+8`, `+248`, `+280`, `+312`, `+344`, `+376`; then calls `0x69b27c` with channel ID **3** at `0x12e24c`. Return zero triggers a diagnostic path. This supports channel-3 registration in manager construction, distinct from subsequent channel-3 receive.

## Replacement contract

Model initialization as two independent completion booleans:
```
on event DPInitDone (0x2af9) if not dp_done:
    run_dp_init_completion_hooks()
    dp_done = true
on event RTEUpdateDone (0x2afa) if not rte_done:
    evaluate_hmi_start_guards()
    rte_done = true
startup_barrier_released = dp_done && rte_done
```
The actions above are **behavioral placeholders**, not proven exact equivalents. The barrier's release is not itself proof that graphics or external IPC are ready. Next investigate producer and delivery of DPInitDone, `0x12dcd4` and `0x68f594`, and the post-barrier manager operations. Avoid reverse-engineering Stage3 shell internals.
