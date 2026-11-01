# GTF2 stage transitions: concrete DP writes and request/event state machine

Verified from local original ARM disassembly `/mnt/data/gtf2-all.dis` and ELF literal words; SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

## New: stage changes update datapool

`0x12a92c(manager, stage, context)` compares requested `stage` (r1) to `manager+0x1c` at `0x12a974–0x12a980`. On the changed-stage path it saves pending stage at `manager+0x20` (`0x12a988`). On the regular update branch `0x12aa18–0x12aa34`, it:

1. stores `stage` at `manager+0x1c` (`0x12aa1c`);
2. calls typed datapool writer `0x69ea0c(0x0200012d, stage)` (`0x12aa24`);
3. calls `0x69ea0c(0x0200013a, stage)` (`0x12aa34`);
4. calls `0x11de04`, `0x11f930`, and `0x12a298`, with an indirect virtual callback between them.

Both datapool IDs are **verified immediate literals**: `[0x12ab70]=0x0200012d`, `[0x12ab74]=0x0200013a`. They are distinct from previously observed background-mode DPID `0x02000136`. Their human-readable property names remain unverified. Some conditional branches of `0x12a92c` bypass these writes; do not assume every invocation writes both.

## New: two separate routes into stage-change action

`0x12ae14(manager, requested_stage, context)` obtains currently requested stage via `0x12997c` at `0x12ae48`, tests both current stage and incoming stage, manipulates a tree of requests and status flags, then invokes `0x12a92c` at `0x12b080` on some branches. It logs `requested view stage: ..., standing requested stage: ..., handle: ...` at `0x12b0b0`.

A separate function ending at `0x12adfc` calls `0x12a92c` directly at `0x12adf4`, after updating `manager+0x18` and calling `0x69ea0c(0x0200015a, manager+0x18)` at `0x12ad9c`. Literal `[0x12ae10]=0x0200015a`. Thus **three concrete DP IDs** are implicated in the StageManager state machine: `0x0200012d`, `0x0200013a`, and `0x0200015a`.

## Branching in event function `0x12ae14`

After obtaining current stage, it accepts current stages 1/2, or stage 5 with incoming stage zero, through one path (`0x12ae4c–0x12ae68`). Other paths set `manager+0x28`, `+0x34`, and may allocate a new request record (`0x12aef0–0x12af50`). The switch on incoming stage values 1..5 (`0x12af54–0x12af78`) modifies flags `manager+0x24` and `+0x30`; a separate switch on current requested stage values 1..6 (`0x12afd8–0x12b004`) selects the next stage passed to `0x12a92c`. Some cases explicitly pass stage zero (`0x12afb0–0x12afc4`, `0x12b020–0x12b038`).

**Important limitation:** these are static code paths. The QEMU log only shows `Unrequest: (1,5)` at 18.430 and `requested view stage: 0` at 18.850. Without LR tracing or logging the incoming stage argument at `0x12ae14`, no single branch can be assigned as the executed one. It is not proven that `Unrequest` alone caused the blanking.

## Targeted runtime tracing

- `0x12a348`: log LR, handle and stage for `Unrequest`.
- `0x12ae14`: log LR, incoming stage r1, current stage via `0x12997c`, flags `manager+0x24/+0x30`.
- `0x12a92c`: log LR, incoming stage r1, previous stage `manager+0x1c`, and whether both DP writes are reached.
- Monitor datapool IDs `0x0200012d`, `0x0200013a`, `0x0200015a` together with `0x02000136` during 17–20 seconds.

This connects the visible stage transition to concrete datapool state, without yet claiming their scene-property names. No Stage3.
