# GTF2 StageManager Unrequest(1,5): call sites and actual meaning

Source: original ARM32 GTF2 disassembly, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`; boot log captured 2026-10-28 with QEMU. This is a static xref analysis; **the exact runtime caller at 18.43 s has not been identified**.

## Runtime evidence

- `17.080`: `DisplayManager: handleLoadingKZBs(), ClusterFull loaded`.
- `18.430`: `StageManager: Unrequest: (1, 5)`.
- `18.850`: `StageManager: requested view stage: 0, standing requested stage: 0, handle: 0`.
- User observes full gauges visible briefly, then disappearing around 18–19 seconds.
- These events are correlated, but the log alone does not prove which code path caused the unrequest or that it alone removes gauges.

## Exact implementation

The string `Unrequest: (%u, %u)` is at `0x7c246a`; literal pointer at `0x12a48c`, referenced by `0x12a3ec` and logging call at `0x12a3f8`. Function entry `0x12a348` receives manager in r0 and **pointer to a handle** in r1; it checks manager byte `+0x31` and searches a tree rooted at manager `+0x04`, keyed by `*(uint32_t*)r1` against node `+0x04`. On match, the log prints node `+0x04` (handle) and `+0x08` (requested stage). Thus `(1, 5)` is handle 1 for stage 5, **not the two arguments of the function**.

At `0x12a3fc–0x12a410`, it maps the removed stage to a recompute flag: stage 1 => 1, stage 2 => 1, otherwise 0. It removes the tree node with `0x129bfc` and decrements count at manager `+0x10`. **For stage 5, this function does not call the recomputation path `0x12997c`/ `0x12a298` at `0x12a440–0x12a474`**. Therefore the later log `requested view stage: 0` is not necessarily a direct recompute inside this Unrequest call; find its separate producer.

## Static callers

Direct `bl 0x12a348` sites:

- `0x117d80`: conditional stage-request handling.
- `0x119880`: ViewManager view-hide/cleanup path, followed by clearing `object+0x18`, `+0x68`, `+0x1c`; preceding operations call view virtual method `+0x30`, `0x117e58`, `0x11511c`, `0x113e50`, `0x120e94`. The string `ViewManager::justHidden` is referenced at `0x1198b8`, indicating the surrounding view transition.
- `0x119bc8`: another ViewManager transition branch; calls view virtual method `+0x30`, `0x11511c`, `0x113e50`, `0x120e94` before unrequest and clears `object+0x68` afterward.
- `0x11a720`: another cleanup path.
- `0x11ab80`, `0x11abd0`: conditional request replacement paths.
- `0x6b76b8`, `0x6b7784`, `0x6b789c`: additional indirect subsystem call sites.

The call at `0x119880` is a strong candidate for a view-hide lifecycle transition but is **not uniquely established as the runtime source** of the `18.430` line.

## Next decisive instrumentation

At entry to `0x12a348`, log `r0`, `r1`, `*(uint32_t*)r1`, `lr` and a timestamp; print the matched node's `+0x04` and `+0x08`. For the observed handle 1/stage 5 event, `lr-4` should identify the precise direct BL callsite (or a wrapper). Instrument the corresponding request creation and the `requested view stage` producer independently. This is preferable to blocking all Unrequest calls, which could break normal view transitions.
