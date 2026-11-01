# GTF2 boot: event-driven transition from EarlyTubes to ClusterFull (detailed log)

Source: user-supplied 1,291,814-byte detailed boot log (`Вставленный текст.txt`). All times below use the timestamp **inside the GTF2 message** (`00:00:SS.mmm`), not the leading console capture timestamp. Line numbers refer to that log.

## Confirmed chronological events

| GTF2 time | Log lines | Event / state |
| --- | ---: | --- |
| 7.610 | 1029 | `eSIDThreadManDPInitDone` |
| 9.680 | 2696 | `eSIDThreadManRTEUpdateDone` |
| 11.950 | 3020 | StageManager `requested view stage: 5, standing requested stage: 5, handle: 1`; `SV_Empty_Startup` aboutToShow at 3018 |
| 13.730 | 3118 | DisplayManager `EarlyTubes loaded` |
| 13.780 | 3125 | DisplayManager `Waiting 3 frames` |
| 13.800 | 3131 | `eEventIdINTERN_Tubes_Show`: `eStateIdVariant_ALL -> eStateIdClusterEarlyTubes` |
| 28.860 | 4739 | `eEventIdINTERN_EarlyTubes_Timeout`: `ClusterEarlyTubes -> EarlyContent_Outer -> EarlyContent_Inner -> ClusterEarlyTubes` (lines 4739–4750) |
| 43.900 | 5960 | The **same timeout transition chain** repeats (lines 5960–5965) |
| 45.650 | 6428 | DisplayManager `ClusterFull loaded` |
| 45.920 | 6430 | DisplayManager `Waiting 3 frames` |
| 45.950 | 6434 | `eEventIdINTERN_ClusterEarlyTubes_Updated`: `ClusterEarlyTubes -> ClusterFull` |
| 45.960 | 6436–6450 | View switch: `MV_ClusterEarlyTubes justHidden`, `Background_grid setVisible(0)`, `MV_ClusterFull aboutToShow` |
| 48.380 | 6846 | `eEventIdClusterFull_Enter`: `Empty -> CenterStage_Visible` |
| 48.400 | 6848–6859 | **Same event** cascades `CenterContentSelectable -> Car -> Car_LVDS_NotActive -> BordComputer` |
| 48.400 | 6861 | ViewManager starts `SV_Empty_Startup -> SV_BordComputer`, fade-out animation |

## New key observation: timeout is a repeated internal state-machine event, not a loading completion

At 28.860 and 43.900 the state machine processes `eEventIdINTERN_EarlyTubes_Timeout` while KZB/texture loads are still underway. It cycles through `EarlyContent_Outer` and `EarlyContent_Inner` back to `ClusterEarlyTubes`. This repeats at ~15.04-second spacing. It does **not** trigger `ClusterFull` and does **not** imply a KZB load failure.

## Separate completion barriers

1. `EarlyTubes loaded` precedes `Waiting 3 frames` and `INTERN_Tubes_Show`.
2. `ClusterFull loaded` precedes `Waiting 3 frames`, `INTERN_ClusterEarlyTubes_Updated`, hiding early tubes and showing full cluster.
3. `eEventIdClusterFull_Enter` occurs **2.43 seconds after** `ClusterFull loaded` (45.650 -> 48.380) and drives the **center content state machine**, not the initial cluster resource switch.
4. `SV_Empty_Startup -> SV_BordComputer` occurs after the center state machine resolves the target state.

The two clocks printed in the same log can be reordered because threads and console output are buffered; rely on GTF2 timestamp plus thread sequence and explicit event names, not console arrival order alone.

## Implications for IAA-compatible replacement

Implement separate gates/states for DP initialization, RTE initialization, EarlyTubes resource ready, full-cluster resource ready, early/full cluster view switch, center-content activation, and actual ViewManager transition. Preserve the recurring early-tubes timeout as a distinct state-machine event. Do not conflate `ClusterFull loaded` with `eEventIdClusterFull_Enter`, and do not use a fixed 15-second delay to force the full-cluster switch.

## Still unverified

The exact binary function emitting each event and the timer registration/reset code are not identified by this log alone. No assertion that the 15-second interval is a hard-coded timer period without disassembly confirmation. The earlier `Unrequest(1,5)` is **not present in this run**; it cannot be assumed to be a mandatory boot step.
