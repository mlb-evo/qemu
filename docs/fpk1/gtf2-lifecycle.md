# GTF2 / FPK1 — lifecycle and execution research

> Status: **initial evidence inventory / open investigation**, 2026-10-28. This document does **not** claim that GTF2 startup order, executable identity, IPC endpoints or graphics APIs have been verified. Keep hypotheses separate from observations.

## Scope

Reconstruct what `gtf2` is, who starts it, at which boot phase, what it loads, how it communicates, which threads it creates, what graphics/display resources it owns, and how it behaves on faults, restart and shutdown. Primary target: **FPK1**. Do not conflate FPK1 with the MHI2 Tegra3 head-unit guest.

## Evidence register

| ID | Finding | Evidence | Confidence / limits |
| --- | --- | --- | --- |
| E-001 | Repository is an experimental QEMU MHI2 Tegra3 fork with QNX HMI, graphics/audio bridges and MOST cockpit support. | [README](../../README.md), [fork notes](../../README.MHI2.md) | Confirmed for MHI2 emulator, **not** GTF2-specific. |
| E-002 | Consolidation records tests of HOST1X/GR2D, native frame sharing, shader translations and host graphics transport. | [CONSOLIDATION](../../tools/mhi2/CONSOLIDATION.md) | Confirmed project context; cannot infer FPK1 GTF2 implementation. |
| E-003 | FPK1 local research scripts belong under `tools/fpk1/research/`; generated/private artifacts under gitignored `build_fpk1/research-artifacts/`; VM logs may be in `build_fpk1/runs/`. | [AGENTS.md](../../AGENTS.md) | Confirmed repository workflow. |
| E-004 | QNX GF architecture (when applicable) uses `io-display` to manage graphics resources, with GF client rendering via `libgf`. | [QNX 6.5 GF guide](https://www.qnx.com/developers/docs/6.5.0SP1/gf/dev_guide/intro.html) | General reference only; **no evidence yet** that FPK1 GTF2 uses GF. |

## Key unknowns (do not silently promote to facts)

1. Is `gtf2` a process name, binary, service, script, module or an alias? Exact case/path/hash/build-ID and firmware version?
2. Which FPK1 image/partition contains it? Which boot script or service manager launches it, with which argv/env/cwd/UID?
3. What must start first? Which resource/service availability conditions gate its startup? Is startup synchronous, retry-driven or event-driven?
4. Which dynamic libraries, config files, fonts, shaders and assets are loaded? In what order?
5. What device nodes, shared-memory regions, sockets, channels, message queues and interrupts does it access?
6. Which graphics stack does it actually use (GF, Screen, EGL/GLES, OpenKODE, proprietary driver or another path)? Which display, layer, buffers and sync primitives?
7. What does its main loop do, which events wake it, and which threads have which priorities?
8. How does it handle display updates, input, CAN/MOST/vehicle data (if any), errors, suspend/resume, shutdown and restart?
9. Which behavior belongs to GTF2 versus other FPK1 services or MHI2 components?

## Boot-to-runtime timeline (unverified skeleton)

| Phase | Event to establish | Required evidence |
| --- | --- | --- |
| T0 | Kernel/IFS starts | boot logs, IFS buildfile/startup entries |
| T1 | Filesystems and prerequisites available | mount table, init scripts, process start timestamps |
| T2 | GTF2 launch requested | exact launcher/config and arguments |
| T3 | Loader resolves executable and shared libraries | binary headers, dependencies, library paths, loader diagnostics |
| T4 | GTF2 initializes devices, IPC and graphics | traces, file descriptors, device/resource logs |
| T5 | GTF2 enters steady state | thread snapshots, CPU/wakeup trace, frame/IPC trace |
| T6 | External event triggers activity | correlated timestamped event and resulting IPC/render actions |
| T7 | Fault, restart, suspend or shutdown | exit codes/signals, watchdog and resource cleanup evidence |

## Collection plan

### Static

- Identify all references to `gtf2` (case-insensitive) across extracted FPK1 firmware, startup scripts, service manifests, binary strings and available docs.
- Record original image, full path, SHA-256, architecture, ELF interpreter, dependencies, symbols, relocations and embedded paths.
- Reconstruct caller/callee relationships and initialization functions from symbols/disassembly; tag guessed function names as hypotheses.
- Correlate startup definitions with filesystem mounts and dependencies.

### Runtime

- Capture a single monotonic boot timeline: process creation, argv/env, parent PID, thread creation, priorities, mounts, IPC endpoints and device opens.
- Take synchronized snapshots before start, during init, first visible frame, idle, input/event and shutdown.
- Correlate process/thread traces with graphics operations, buffer ownership and display output.
- Repeat cold boot and restart; compare expected versus observed order and durations.
- Keep original logs and binary artifacts outside git; commit only research scripts and sanitized findings.

### Deliverables

1. **Identity sheet**: binary path/hash/version, role and ownership.
2. **Startup DAG**: launcher → dependencies → GTF2 initialization.
3. **Timeline**: measured timestamped stages and delays.
4. **IPC map**: endpoints, producers, consumers and message formats.
5. **Graphics pipeline**: producer → memory/buffers → compositor/display.
6. **Thread map**: responsibilities, scheduling and blocking points.
7. **Failure matrix**: missing dependency, crash, restart, suspend/resume.
8. **Evidence index**: each assertion links to an exact source, trace or disassembly address.

## Working rules

- Never describe MHI2 host graphics behavior as observed FPK1 GTF2 behavior without direct FPK1 evidence.
- Distinguish `CONFIRMED`, `INFERRED`, `UNKNOWN`, `DISPROVEN` for every lifecycle claim.
- Every timing claim requires a clock basis and timestamped evidence.
- No firmware binaries, proprietary assets, raw sensitive traces or generated outputs in this PR.
- Add new evidence and corrections here in follow-up commits.

## Firmware evidence — 2026-10-28 (Drive archive)

Source: private Drive folder `fpk1-evo`, archive `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip` (45,883,438 bytes). **Do not commit firmware content.** Inspection was read-only against the ZIP members.

- ZIP contains 66 entries, including `KI_FPK_AU536/gss-stage1/8/default/stage1_ifs.img` (2,060,482 bytes) and `KI_FPK_AU536/gss-stage2/8/default/stage2_ifs.img` (23,056,578 bytes).
- SHA-256 of `stage1_ifs.img`: `67628acca2d93f4aac0d60dc06b0cad01184c10ec300325932560fe8bc6b378a`.
- SHA-256 of `stage2_ifs.img`: `c705b591ac0291b7a901f714cadef1e66ba7e0f8741aa5e1b1671d7ee9126f7c`.
- Raw, **unextracted** stage1 image contains ASCII `gtf2\0` at file offset **497312** (decimal), near `kdgui_2dmgr`. This is an observed byte sequence, not yet a verified launcher entry.
- Raw, **unextracted** stage2 image contains `gtf2\0` at **8467400**, `gtf2q\0` at **8503197**, and a `gtf2` occurrence at **9182669** within a metadata-like text fragment containing `DESCRIPTION=HMI applic`, `2018-06-22CEST-15:34:40`, `USER=jenkins`, and `TCID=RL_QNX_OS_650SP1_MMX2_17.52`. Some characters between fields are binary/encoded: do **not** assume this is an intact plain-text manifest.
- Other stage2 case-insensitive GTF2 occurrences include offsets **8506374**, **9090481**, **9109606**, **9290588**. Raw compressed/packed image byte offsets are **not** ELF file offsets or virtual addresses.
- No archive member is directly named `gtf2`; the archive wraps stage images, so internal IFS unpacking is required to identify the executable and startup commands.

### Next proof step

Use a QNX-aware IFS/image unpacker on `stage1_ifs.img` and `stage2_ifs.img` (accounting for the `HSP` container header); identify startup scripts and `gtf2` ELF with provenance, then map `gtf2q`, `kdgui_2dmgr`, and actual IPC relationships. Until that step, **do not claim** that `gtf2q` is a helper process or that `gtf2` starts in stage1 or stage2.

## Verified extraction — 2026-10-28

The repository already provides the correct implementation: `tools/fpk1/verify_sifs_partitions.py`, `tools/fpk1/inspect_stage2_catalogs.py`, and `tools/fpk1/research/hmi/extract_stage2.py`. These decode `CIFS` from HSP offset `0xba`, reconstruct partition data from `stage2_ifs.img` **and** `stage2_nand.img`, verify Adler-32 block frames and decode LZO. Earlier speculation that Stage2 could not be reconstructed was superseded by this existing research.

Independently reproduced locally with system `liblzo2.so.2` (`lzo1x_decompress_safe`), checksum validation, and the documented SIFS partition table:

- `STAGE2.1` reconstructed to **24,434,456 bytes**, `STAGE2.2` to **29,056,564 bytes**; both match their `imagefs\\x04` declared lengths.
- `STAGE2.1/bin/gtf2` extracted as **10,180,269 bytes**, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.
- `gtf2` is a stripped ARM32 little-endian EABI5 dynamically linked ELF, with interpreter `/usr/lib/ldqnx.so.2`, entry point `0x0010f300`, executable LOAD virtual base `0x00100000`.
- `DT_INIT=0x0010d774`, `DT_FINI=0x007bca98`; `DT_INIT_ARRAYSZ=1408` bytes (352 32-bit entries). This is not a count of runtime threads.
- Direct `DT_NEEDED` dependencies: `libeal.so`, `libdisplayinit.so`, `libpersistency.so`, `libair.so`, `libFor.so`, `libKD.so`, `libGLESv2.so`, `libEGL.so`, `libnvddk_2d.so`, `libnvrm.so`, `libnvrm_graphics.so`, `libnvos.so`, `libnvwsi.so`, `libnvcwm.so`, `libnvddk_2d_v2.so`, `libz.so.2`, `libmostappsocket.so`, `libiplcommon.so`, `libosal.so`, `libutil.so`, `libcomm.so`, `libc.so.3`, `libm.so.2`, `libsocket.so.3`, `libecpp-ne.so.4`.
- `STAGE2.1/bin/gtf2_error_fallback.sh`: SHA-256 `a89d91b0c272185cbd3b400aedff160c4e6960a06a09356972c0e40aff8c1bc5`. It sleeps 30 seconds, exits if `/tmp/stage3_started` exists, otherwise prints an error and invokes `/bin/start_stage3.sh`.
- `STAGE2.1/bin/start_stage3.sh`: SHA-256 `c4cc55cda997a991ce808c688432eaa3094ab7838675c53b5a9f6352d2c45dc2`. It guards against repeated invocation using `/tmp/stage3_started`, creates that marker, waits for `/stage3/bin/stage3.sh`, then executes it through `/bin/ksh`.
- The two scripts were read as original extracted contents. **No runtime execution or launch caller has yet been observed.**

### Corrected status

`gtf2` is **confirmed** to be an executable in STAGE2.1. NVIDIA/EGL/GLES/KD libraries are direct dependencies, not proof of particular initialization order. The fallback path is confirmed in shell text, but actual scheduling and failure triggers remain unknown. Next: inspect Stage1 startup and Stage3 startup scripts; map the caller that starts `gtf2`, then static-disassemble its ELF entry and constructors.
