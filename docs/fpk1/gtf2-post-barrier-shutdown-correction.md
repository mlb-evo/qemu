# GTF2 startup barrier leads to shutdown sequence, not rendering

Source: original Stage2.1 `bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. ARM instruction and literal-string inspection. This corrects `gtf2-post-barrier-handoff` hypothesis and prior lifecycle summaries.

## Confirmed post-barrier diagnostics

`0x12e380` calls `0x12e0a8` at `0x12e3e8`; that waits for `DPInitDone` and `RTEUpdateDone`. On return:

- `0x12e3f4`: `0x12ddc8(manager, config[0])`. String at `0x7c32e5`: `Setting Developer Build DTC: %s`; failure string at `0x7c3305`: `Can't set Developer Build DTC. HmiComm not initialized!`. `0x12ddc8` checks global HmiComm availability (`0x68dae8`), obtains object through `0x68dbb0`, then calls `0x6986e0`. The configuration boolean is passed through. The exact low-level field write remains to be inspected.
- `0x12e424`: `0x12dd38(manager, derived_bool)`. String at `0x7c333d`: `Setting GEM Enabled flag to %u`; failure string at `0x7c335c`: `Can't set the GEM Enabled flag. HmiComm not initialized!`. It checks HmiComm, accesses via `0x68dbc8`, and tail-calls `0x6919f8` with inverted boolean. The effective value is derived from three config bytes; instruction-level simplification at `0x12e3f8–0x12e420` gives `derived_bool = config[0] || config[1] || config[2]` for byte flags 0/1.
- `0x12e430`: `0x12de3c()` performs operations with literal signal values 15 and 2 through `0x10e024`, then `0x10d9e8`; returned value is passed to `0x69992c`.
- `0x12e474`: worker teardown through `0x12de74`.
- `0x12e478`: cleanup through `0x68deb4`.
- `0x12e498–0x12e4bc`: diagnostic `Starting shutdown, signal=%d.` (string `0x7c34c5`) then virtual calls through global `0xab5618` slots `+0x10`, and returned object's slot `+0x44` with arg 1. Another literal `Shutdown complete.` at `0x7c34e3` is referenced by the earlier diagnostic block at `0x12e48c`; the exact branch and ordering should not be inferred solely from string proximity.

**Conclusion:** The post-barrier block is shutdown/cleanup, not a steady-state render loop. The previous descriptions of the virtual calls as an unresolved *render handoff* are superseded; their exact implementation still needs vtable resolution. Worker threads may host the persistent HMI loops, but that remains to be proven by tracing thread entrypoints.

## Follow-up

Trace HMI worker `0x68c860` / `0x114650` main processing loop and stop condition; inspect whether `0x12e0a8` can return only on shutdown or on normal startup; reconcile the apparent `DPInitDone`/`RTEUpdateDone` barrier with the shutdown path using original diagnostics and runtime traces. The latter is a critical consistency check before implementation.
