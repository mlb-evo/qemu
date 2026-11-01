# Stage 5 unrequest vs subsequent stage-0 log: distinct code paths

Evidence: original ARM32 `gtf2` and QEMU startup log, observed gauges disappear around 18–19 seconds.

## Directly verified code

The `Unrequest: (%u, %u)` line is emitted by `0x12a348` at `0x12a3f8`, where the two values are node fields `+4` (request handle) and `+8` (stage). It deletes the matching tree entry. For stage 5, `0x12a3fc–0x12a438` sets local recomputation flag to zero, so this function does **not** invoke its conditional `0x12997c` / `0x12a298` path.

The later `requested view stage: %d, standing requested stage: %d, handle: %d` string is at `0x7c26f1`, referenced by literal at `0x12b0d4`. It is logged by **a separate function**, `0x12afxx` (logging at `0x12b0b0`), after calling `0x12a92c` at `0x12b080`. The logger separately calls `0x12997c` at `0x12b098` to obtain the current requested stage; it does not merely echo the stage removed by Unrequest.

This function contains a state/event switch at `0x12afd8–0x12b084`. One branch explicitly invokes `0x12997c`, subtracts one, checks <=5 and jumps via table `0x12aff0–0x12b004` to distinct state-transition actions; other branches set state bytes `manager+0x24` or `+0x30` before calling `0x12a92c`. Therefore the stage-0 log at 18.850 is an **independent state transition**, not proof that Unrequest(1,5) itself recalculated stage to 0.

## Runtime sequence

- 17.080: `ClusterFull loaded`
- 18.430: `Unrequest: (1, 5)`
- 18.850: `requested view stage: 0, standing requested stage: 0, handle: 0`
- User confirms gauges are initially fully visible and disappear approximately then.

This makes the transition mechanism a strong lead but does not uniquely identify which of the several direct callers of `0x12a348` was executed, or whether a second state update is the immediate cause of blanking.

## Instrumentation to identify both actors

1. At entry `0x12a348`, record LR, handle, matching node stage and timestamp. `LR-4` identifies the callsite of a direct ARM BL.
2. At entry of the `0x12afxx` state/event dispatcher (and before `0x12b080`), record LR, selector/event, `manager+0x18`, `+0x24`, `+0x30`; at `0x12b0b0` record the three logged values.
3. At `0x12a92c`, record old `manager+0x1c`, new requested stage in r1 and source LR. This is where stage changes are acted on.
4. Compare the traces against 18.430 and 18.850. Do not globally suppress Unrequest without isolating its caller.

## Status

Verified separate producers for the two diagnostic messages, and identified the stage-change action function `0x12a92c`. Exact runtime caller and stage-0 trigger remain unresolved. No Stage3.
