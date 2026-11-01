# Stage3 startup: consolidated implementation contract (existing evidence)

This file **reconciles existing research**; it does not claim a new firmware extraction or QEMU run. Detailed disassembly and runtime observations are already in [gtf2-lifecycle.md](gtf2-lifecycle.md) and [fpk1-firmware-research.md](../fpk1-firmware-research.md). Do not re-reverse-engineer these proven links.

## Boot dependency and responsibility

1. Stage1 `proc/boot/startup.script` has 47 decoded records (36 external commands, nine waits, console reopen, symlink). It initializes QNX/hardware, launches background `mount_nand.sh`, waits for `/bin/gss_ipc`, then starts Stage2 services including `gss_ipc`, `broker`, `kdgui_2dmgr` and **`gtf2`**. This is script order, not guaranteed service readiness.
2. `mount_nand.sh` waits for `/dev/emmc0`, mounts QNX6 entries; `/etc/fstab` associates `/dev/emmc0t177.6` with `/mnt/stage3` read-only. The Stage2 launcher waits separately for `/stage3/bin/stage3.sh`: mount availability and GTF2 activation are independent.
3. GTF2 is the original Stage2.1 executable `bin/gtf2` (SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`), not a Stage3 executable.
4. The normal Stage3 trigger is GTF2 function `startEfsDriver()` at **`0x699594`**. Three independently found direct ARM `BL` callers: `0x122eac` (asset-loading path), `0x130794` (delayed HMI path), `0x692f20` (cold crank path). The routine references literal `/bin/start_stage3.sh` at `0x88fba9` and calls OSAL `ProcessTNG::start()` through PLT `0x10e708`. This establishes an attempted process launch, **not successful execution**.
5. `/bin/start_stage3.sh` checks `/tmp/stage3_started`, creates it, waits for `/stage3/bin/stage3.sh`, then runs it using `/bin/ksh`. The marker is an *attempt guard*, **not a Stage3-ready signal**. It can exist while waiting for the mount/script or after a failed Stage3 run.
6. Stage1 also starts `gtf2_error_fallback.sh` in the background. It sleeps 30 seconds after its own start, checks the same marker, and invokes `start_stage3.sh` if absent. The marker check/create is not atomic across simultaneous starters.
7. Stage3 script chain `/stage3/bin/stage3.sh` → `/stage3/bin/startup-common.sh` is previously identified; detailed commands, subprocess order, wait conditions and failure semantics still need to be enumerated from original Stage3 filesystem.

## GTF2 asset-loading branch (already decoded)

The existing analysis of `handleLoadingKZBs()` records:
- `EarlyTubes` requested and handled; an explicit frame-wait precedes the request for `ClusterFull`.
- When `this+0xdf7 != 0 && this+0xdf8 == 0`, the branch logs `ClusterFull loaded`, calls internal helper `0x121498`, invokes `startEfsDriver()` at **`0x122eac`**, then sets `this+0xdf8 = 1`.
- The separate `3D Car` asset flow and the delayed-HMI branch are not to be conflated with Stage3 readiness.
- The delayed path reaches `0x130794` only after guards at `0x13067c` and `0x13066c`; the RTE update-done event is an upstream trigger, not unconditional Stage3 launch.

## Operational state model for an IAA-based replacement

| State | Evidence-based entry | Transition / action | Important limitation |
|---|---|---|---|
| S0 Stage1 services starting | QNX startup script | Start IPC/broker/graphics/GTF2 and fallback | Spawn order is not readiness order |
| S1 GTF2 activation pending | GTF2 started | IPC/mode handshake; initiate UI asset loading | Mode-request race not resolved |
| S2 Asset loading | `EarlyTubes` and `ClusterFull` flow | After the documented ClusterFull branch, attempt Stage3 launch | Branch conditions are known; exact asset completion predicate needs more work |
| S3 Stage3 launch requested | Any of the three GTF2 call sites, or fallback | Invoke `start_stage3.sh`; check/create marker | Marker means attempt, not success |
| S4 Stage3 script available | `/stage3/bin/stage3.sh` exists | Execute Stage3 scripts | Commands/readiness checks not yet enumerated |
| S5 Stage3 services ready | **UNKNOWN** | Must be established from actual Stage3 service contracts | Do not infer readiness from script invocation |

This is a **partial state model**, not a fully verified finite-state machine.

## Existing runtime evidence, not new testing

A previously documented synthetic QEMU run saw eMMC at 1.0 s, display init at 1.8 s, `gss_ipc` at 2.8–5.8 s, GTF2/EAL at 10.8 s, AliveManager failures at 62.5 s, and fallback Stage3 launch at 65.1 s. These are host elapsed times, not guest timestamps or stock-device timing. Another run answered GSS mode request `1/2` and activated GTF2 at 6.2 s. Hypothesis: mode handshake impacts readiness; no causal proof yet.

## Next *nonduplicative* investigation

Read the actual **Stage3** `/bin/stage3.sh` and `/bin/startup-common.sh` via the existing QNX6 extractor (`tools/fpk1/inspect_stage2_catalogs.py --with-stage3`, using `probe_qnx6_root.py`); enumerate each spawned service, wait, mount and environment mutation. Correlate these with the already-proven three GTF2 launch triggers, and inspect **only** the unresolved `ClusterFull` completion gate, OSAL process-start failure path and Stage3-ready signal. This yields a boot DAG and implementable readiness contract without redoing proxy vtables or the Stage1 decode.
