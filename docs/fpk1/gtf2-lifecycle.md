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

## Startup, activation and rendering: reconciliation with existing FPK1 research

**Important correction:** `docs/fpk1-firmware-research.md` on the base branch already contains decoded Stage1 startup records, actual QEMU boot measurements and GTF2 function-level analysis. These results supersede earlier UNKNOWN statements in this document. The observations below are drawn from that existing research, not from a fresh VM run in this PR. Source of truth: [FPK1 firmware research](../fpk1-firmware-research.md), particularly “Complete Stage1 ZV/LZF reconstruction and startup script”, “Graphics: host1x fixes”, and “diagnosis and swdlclient: Stage3 starts too late”.

### Proven startup ordering (binary Stage1 QNX script)

Stage1's validated imagefs holds `proc/boot/startup.script` (3,808 bytes), decoded into **47 records: 36 external commands, nine waits, one console reopen and one symlink**. Relevant startup dependencies/order:

1. QNX `procnto` handoff, runtime loader symlink `/usr/lib/ldqnx.so.2`, logging and hardware services.
2. Serial, NVIDIA memory/SKU/clock/GPIO/OS, I2S/I2C/audio/display initialization.
3. Background `ksh /bin/mount_nand.sh` waits for `/dev/emmc0`, then `mount -t qnx6 -a`; `/etc/fstab` maps `/dev/emmc0t177.6` to `/mnt/stage3` (ro), among other partitions.
4. Wait for `/bin/gss_ipc`, then launch Stage2 services including `gss_ipc`, `broker`, `kdgui_2dmgr`, **`gtf2`**, audio/MOST/tracing.
5. Arm background `ksh /bin/gtf2_error_fallback.sh`, then `tinit`.

The boot script *does* arm the fallback. The fallback sleeps **30 seconds after its own launch**, not necessarily 30 seconds after system reset; the Stage3 marker prevents a duplicate handoff in normal serial execution, but the shell check and touch are not atomic.

### GTF2 → Stage3 call graph (existing disassembly evidence)

- `gtf2::startEfsDriver()` at **0x699594**, log `Started NAND fs driver script`, is the normal non-fallback Stage3 starter.
- Called from `handleLoadingKZBs()` after `ClusterFull` loading (**0x122eac**); also reachable from delayed-HMI-start path (**0x130794**) and `GssMan2HMIReplyImpl::enterColdCrank()` (**0x692f20**).
- It leads to `/bin/start_stage3.sh` → `/stage3/bin/stage3.sh` → `/stage3/bin/startup-common.sh`.
- The current research has not established why `ClusterFull` loading can miss the fallback deadline.

These addresses are **GTF2 ELF virtual addresses**, not raw ZIP offsets. Further independent control-flow verification of each call edge is a follow-up.

### Activation and AliveManager

Existing analysis identifies framework agent **`hmi` (ID 200)** as GTF2's alive client. `gss_ipc`/peer activation is a prerequisite to the HMI becoming ready; merely spawning the ELF is insufficient.

Two previously recorded runs show a reproducible distinction:
- `20261027-103922`: peer sent `GSS_MODE_REQUEST 1/0`, then `1/2` 0.2 seconds later. Only the first was answered. GTF2 printed nothing before Stage3, `hmi` failed, despite a running link (7,424 cycles).
- `20261027-104450`: the `1/2` request was answered, GTF2 activated at **6.2 seconds**, and `hmi` did not fail.

**Hypothesis:** a missed/ignored mode request can stall activation. The exact `gss_ipc` decision and scheduling race remain unverified.

### Measured prior boot timeline (host seconds; one documented run)

| Host time | Previously observed event |
| --- | --- |
| 1.0 s | eMMC enumerated |
| 1.8 s | `display_init: successfully set modes` |
| 2.8–5.8 s | `gss_ipc` startup |
| 8.0 s | serial login prompt |
| 10.8 s | GTF2/EAL `Variant: fpk1`; `display_create_window` fails |
| 62.5 s | AliveManager declares `hmi`, `kdgui_2dmgr`, `diagnosis`, `swdlclient` failed |
| 65.1 s | GTF2 fallback log and Stage3 launch |
| 65–71 s | Stage3 services, USB networking, INIC, challenge port |

These are **host elapsed times from a previous synthetic QEMU boot**, not guest monotonic timestamps and not new measurements. The nominal 30-second sleep does not imply fallback at host t=30s; emulation time and launch origin matter.

### Graphics dependencies and observed blockers

- Native KD/NVIDIA path: `kdgui_2dmgr` REPLY-blocked on `devg-nvrm` host1x syncpoint work. With `TEGRA_GR3D_DISCARD=1` and host1x wait/syncpoint fixes, GTF2 creates a **1440×540** window and dc-a scans a black frame; this does **not** mean GR3D rendering is implemented.
- Optional EGL/GLES host bridge allows GTF2/EAL to upload shader binaries, textures and programs, but earlier runs saw no GTF2 draw/swap; `kdgui_2dmgr` failed during EGL startup. A black frame is not proof that GTF2 completed initialization.
- Existing research later added AR20→GLSL translation for NVIDIA shader binaries and validated 193 KZB material pairs. Shader readiness and service activation are distinct bottlenecks.
- `diagnosis` and `swdlclient` are started by Stage3, so delayed GTF2-driven Stage3 launch can cause their AliveManager deadlines to be missed.

### Static ELF initializer boundary

`DT_INIT=0x10d774`; `DT_INIT_ARRAY=0xa644dc`; `DT_INIT_ARRAYSZ=1408` bytes = **352 entries**. These are **potential constructors**, not proven GTF2-specific phases or a known order of framework initialization. Next static step: parse actual array pointers and relocations, annotate constructor callees and relate them to `main`/activation and the addresses above. Do not assign functionality to constructors from position alone.

### Follow-up work

1. Recover all 352 initializer pointers and classify by target (ELF text/PLT/invalid/relocated); produce address-index manifest with evidence.
2. Disassemble the entry point, `DT_INIT`, `startEfsDriver`, `handleLoadingKZBs`, `enterColdCrank`, and mode request handling.
3. Instrument `gss_ipc` request/response timestamps, GTF2 `hmi` Alive registration, `ClusterFull` completion, Stage3 marker, and KD/GL calls in a single guest-clock trace.
4. Compare successful activation vs dropped `1/2` request under identical boot flags, keeping original trace artifacts out of Git.

### Constructor inventory: directly checked against extracted ELF

The ELF's second `PT_LOAD` maps virtual `0x00a644dc` to file offset `0x009634dc`. The 1,408-byte `DT_INIT_ARRAY` contains **352 nonzero, distinct ARM32 function pointers**, with observed minimum `0x0010f48c` and maximum `0x007bbdf4`. First eight targets: `0x10f48c`, `0x10fb48`, `0x114ff8`, `0x115fb8`, `0x11616c`, `0x116e34`, `0x117b38`, `0x11bae8`. These are raw pointers from the original extracted ELF; no constructor function names or call ordering beyond array order are asserted. Reproduce the complete JSON inventory with:

```sh
python3 tools/fpk1/research/gtf2/inspect_init_array.py \
  build_fpk1/research-artifacts/stage2/STAGE2.1/bin/gtf2 \
  --output build_fpk1/research-artifacts/gtf2-constructors.json
```

The research script is source-only and validates file-backed `PT_LOAD` mappings; do not commit the extracted binary or the JSON output.

### Independent direct-call verification (2026-10-28)

The extracted original `STAGE2.1/bin/gtf2` was scanned at four-byte ARM-state instruction alignment within its executable ELF `PT_LOAD`. The instruction encoding `BL immediate` at **exactly three** locations resolves to `startEfsDriver() = 0x699594`:

| Instruction address | ARM branch target | Prior research context |
| --- | --- | --- |
| `0x122eac` | `0x699594` | `handleLoadingKZBs()` / `ClusterFull` |
| `0x130794` | `0x699594` | delayed HMI start |
| `0x692f20` | `0x699594` | `GssMan2HMIReplyImpl::enterColdCrank()` |

This independently confirms the **direct branch encodings**, while the symbolic names are taken from the existing reverse-engineering notes. It does **not** prove that any call site executes in a given run or exclude indirect calls. The branch-scan method can interpret inline data as instructions; full disassembly and basic-block validation remain follow-up work.

Reproduce without committing the binary:

```sh
python3 tools/fpk1/research/gtf2/scan_direct_calls.py \
  build_fpk1/research-artifacts/stage2/STAGE2.1/bin/gtf2 \
  --target 0x699594
```

The same scan finds a direct `BL` at `0x6995a0` targeting `0x699530` in the prologue of `startEfsDriver()`; that callee is not yet semantically identified.

### Inside `startEfsDriver()`: verified disassembly and string cross-references

Further direct examination of the extracted ELF with LLVM ARM disassembly (using a **local, non-committed** ELF copy with a synthetic `.text` section because the QNX executable has no ordinary allocated section headers) gives these concrete details:

- `0x699594`: function prologue `push {r4,r5,r6,r7,lr}`, allocates 60 bytes of stack.
- `0x6995a0`: calls `0x699530`, which initializes a stack-local helper; do not assign a class/type without further RTTI or call analysis.
- `0x6995a4–0x6995b0`: reads a global byte at **0xdb0f38** and branches to `0x699720` when nonzero (a repeated-call branch).
- `0x6995b4–0x6995c0`: reads a global pointer at **0xdb0f88** and branches to `0x6995e0` when null; otherwise follows a different repeated/in-progress path.
- `0x6995e8`: loads the literal pointer **0x88fba9**, whose NUL-terminated bytes are `/bin/start_stage3.sh`, then calls `0x10e7bc` at `0x6995f0`.
- `0x6995f4`: passes immediate **160** to `0x10dcac`; the returned object is initialized via multiple calls and stored in the global pointer at `0xdb0f88` by `0x6996e8`.
- `0x6996f4`: calls `0x10e708` with that object; `0x699714` conditionally calls `0x10e264` for a diagnostic.
- `0x699748–0x699758`: cleanup and return, with `r0` set from `r4`; one path returns zero and another one, but the exact semantic interpretation of the result needs callee analysis.

Verified string literals in the **original ELF** (all virtual addresses):
- `0x88fba9`: `/bin/start_stage3.sh`
- `0x88fb82`: `startEfsDriver() called multiple times`
- `0x88fbbe`: `Started NAND fs driver script. PID: %i`
- `0x88fbe5`: `startEfsDriver() already called and finished. Ignoring.`

This establishes a *direct code-to-string reference* to the Stage3 launcher, an in-function repeated-call check, and an object-oriented process-start path. It does **not** yet identify the exact API behind `0x10e708` or prove a successful spawn in any particular VM run. The global at `0xdb0f38` is a guard **candidate**; its exact semantics require tracing writes.

A stock `llvm-objdump -d` on the original stripped QNX ELF prints no instructions for this range because it contains only `QNX_info` and `.shstrtab` section headers. Reproduction must disassemble the executable `PT_LOAD` using virtual address `0x100000`, or add a synthetic section header to a **temporary copy** without changing the load segment bytes. Never commit that copy.

### Resolved dynamic linkage: `ProcessTNG::start()` (2026-10-28)

This section **resolves** the previously unknown `0x10e708` callee and corrects the characterization of `0x10e7bc`. The original stripped ELF has no conventional `.text` section header, but executable `PT_LOAD` contains a standard ARM PLT. The `DT_JMPREL=0x10c52c`, `DT_PLTRELSZ=0x1248`, `DT_SYMTAB=0x10150c`, and `DT_STRTAB=0x1044ec` dynamic entries permit independent symbol resolution:

| PLT entry | GOT slot | JUMP_SLOT symbol (ELF mangled) | Meaning |
| --- | --- | --- | --- |
| `0x10e708` | `0xa655dc` | `_ZN4osal10ProcessTNG5startEv` | **`osal::ProcessTNG::start()`** |
| `0x10e7bc` | `0xa65618` | `_ZN3ipl12basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEEC1EPKcRKS4_` | **`ipl::basic_string<char,...>::basic_string(char const*, allocator const&)`** |

For both PLT entries, the ARM instruction sequence constructs the GOT address using PC-relative `add` and `ldr pc, [r12, #imm]!`; the GOT slots match relocation records **330** and **345**, with symbol indices **437** and **455** respectively. This is stronger evidence than proximity to strings or inferred C++ names.

The actual Stage3 spawn chain is therefore:

```text
gtf2::startEfsDriver()  [0x699594]
  -> construct IPL string from "/bin/start_stage3.sh" [0x10e7bc]
  -> construct/configure OSAL ProcessTNG object [exact constructors not fully resolved]
  -> osal::ProcessTNG::start() [PLT 0x10e708]
  -> libosal.so implementation [not disassembled here]
```

`ProcessTNG::start()` **does not itself prove successful spawn**: return handling, PID assignment, OSAL implementation and the global duplicate-call guards require separate analysis. The earlier assertion that `0x10e7bc` was an unidentified helper is superseded: it is specifically an IPL string constructor.

#### Reproduction notes

Read the ELF program headers and dynamic entries rather than relying on section names. For the original ELF SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`, executable `PT_LOAD` begins at VA `0x100000` / file offset zero. `DT_JMPREL` uses ELF32 `Elf32_Rel` entries (8 bytes); each relocation's `r_info >> 8` is the symbol index. Resolve `st_name` via `DT_STRTAB`. For `0x10e708`, the PLT slot is `0xa655dc`, matching the `ProcessTNG::start` JUMP_SLOT.

**Next:** extract only the original `libosal.so` from the validated Stage2 catalog, inspect its exported `ProcessTNG` constructor/start symbols and disassemble `start()` to establish `spawn`/PID/error semantics. Keep firmware libraries out of Git.

## GTF2-owned application architecture (scope: executable only)

**Scope decision:** Do not reverse-engineer third-party library internals. Treat OSAL, EAL, KD, and IPC proxy implementations as opaque calls. The research target is **GTF2's own state, handlers, data loading, view switching, and event loop**. The preceding PLT/OSAL material is historical linkage verification, not a workstream.

### Internal components supported by original ELF diagnostics

The original GTF2 executable (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`) contains the following NUL-terminated diagnostics; the hex coordinates here are **file offsets**, not ELF virtual addresses. Presence of a log string establishes a code/data anchor, not a proven runtime event.

| Component | GTF2-owned role / diagnostic evidence |
| --- | --- |
| `GssMan2HMIReplyImpl` | `activate()`, `deactivate()`, `enterColdCrank()`, `leaveColdCrank()`, `coldCrankRep()`, `switchDisplayBacklight()`, `persistentData()`, `sendPersistentData()` |
| `handleLoadingKZBs()` | Requests `EarlyTubes`, waits a frame count, requests `ClusterFull`, reports `ClusterFull loaded`, and requests/reports `3D Car` |
| `CHMIGTFAssetManager` | KZB merge/attach, batch completion, asynchronous `KZBListener::process`, unexpected merge events/results |
| `ViewManager` | `handleViewSwitchCenter`, `doSwitch`, `aboutToShow`, `justHidden`, context animation |
| `BaseViewManager` | `processEvent(DP)`, `processEvent(StateMachine)`, `processEvent(Application)`, layout and render-property update |
| Version screen controller | Key dispatch, speed-threshold checks, popup show/hide, timer and state-machine events |
| Screenshot controller | CAN screenshot trigger and `kdgui_2dmgr/takeScreenshot` callback path |

Selected exact log anchors:

| File offset | Original GTF2 diagnostic |
| --- | --- |
| `0x6c15ac` | `handleLoadingKZBs()` |
| `0x6c1650` | `handleLoadingKZBs(), EarlyTubes loaded` |
| `0x6c1677` | `handleLoadingKZBs(), ClusterFull loaded` |
| `0x6c169f` | `handleLoadingKZBs(), 3D Car Loaded` |
| `0x6c16c8` | `handleLoadingKZBs(), Requesting Early Tubes` |
| `0x6c16fc` | `handleLoadingKZBs(), Waiting %i frames` |
| `0x6c1723` | `handleLoadingKZBs(), Done waiting -> Requesting Cluster Full` |
| `0x6c1760` | `handleLoadingKZBs(), 3D Car Requested` |
| `0x6c3b0f` | `Delay the HMI start by %u ms.` |
| `0x6c3b9a` | `Non-ECL Mode Enabled. Starting HMI immediately.` |
| `0x6beb58` | `GSS_GTF_ViewManager` |

**Working hypothesis, not a proven state machine:** an activation callback may select immediate/delayed HMI startup; asset loading advances through early tubes, cluster and 3D car, while event handlers drive views and data updates. String order in `.rodata` does **not** establish control-flow order; it must be checked with code cross-references and conditional branches.

### Reproducible evidence extraction

```sh
python3 tools/fpk1/research/gtf2/inspect_hmi_logic.py \
  /path/to/extracted/STAGE2.1/bin/gtf2 \
  --output build_fpk1/research-artifacts/gtf2-hmi-anchors.json
```

This read-only source script searches a small, explicit list of diagnostic strings and records offsets, without copying firmware content into the repository. Output remains local and ignored.

### Next GTF2-only code analysis

1. Locate ARM code references to the eight `handleLoadingKZBs` strings, identify the owning function's entry/basic blocks and conditionals, and draw a **branch-supported** resource-loading state diagram.
2. Locate `GssMan2HMIReplyImpl::activate/deactivate/enterColdCrank` log references and identify changes to GTF2-owned state; leave IPC proxy implementation opaque.
3. Follow `CHMIGTFAssetManager` completion callbacks into the view manager and any Stage3 initiation; distinguish resource request, merge completion and view readiness.
4. Map `BaseViewManager::processEvent` dispatch by source (DP/state-machine/application) and the view-switch transition functions.
5. Only after static mapping, compare with a guest-clock trace from QEMU; record evidence separately from hypotheses.

Do **not** expand this into a survey of `libosal.so`, `libeal.so`, `libKD.so` or other library internals.

### `handleLoadingKZBs()`: ARM branch-supported internal state (2026-10-28)

**Directly disassembled** original ELF SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. The ARM function begins at **0x122c54** (`push {r4,r5,r6,r7,r8,lr}`; `r4 = r0`, the current object). These are GTF2-owned code paths, not library internals.

| Object byte | Read / write evidence | Working semantic label |
| --- | --- | --- |
| `this+0xdf4` | checked at `0x122c80`; set at `0x122dc4` | terminal/abort guard (exact meaning TBD) |
| `this+0xdf5` | checked `0x122f28`; set `0x122fec` | `EarlyTubes` requested |
| `this+0xdf6` | checked `0x122dec` and `0x123000`; set `0x122e5c` | `EarlyTubes` loaded/handled |
| `this+0xdf7` | checked `0x122e60` and `0x122ff4`; set `0x12332c` | `ClusterFull` requested |
| `this+0xdf8` | checked `0x122e6c` and `0x123340`; set `0x122eb4` | `ClusterFull` loaded/handled |
| `this+0xdf9` | checked `0x122eb8` and `0x123334`; set `0x123480` | 3D car requested |
| `this+0xdfd` | checked `0x122cac` | gate selecting earlier vs subsequent loading path; meaning TBD |

**Observed branch structure:**

1. `0x122c80`: if `+0xdf4 != 0`, exit. Two preliminary internal calls and another gate `+0xdfd` determine whether the function enters the completion handling at `0x122de0` or an earlier path at `0x122cb8`.
2. `0x122de0–0x122e5c`: if `+0xdf5 != 0 && +0xdf6 == 0`, log `EarlyTubes loaded`, invoke the internal resource path using `EarlyTubes` and `DisplaySupervisor.kzb`, then mark `+0xdf6 = 1`.
3. `0x122e60–0x122eb4`: if `+0xdf7 != 0 && +0xdf8 == 0`, log `ClusterFull loaded`, call internal function `0x121498` with the `ClusterFull` literal, then **`BL 0x699594` at `0x122eac`** (`startEfsDriver()`), then mark `+0xdf8 = 1`. This is a verified call ordering in the branch, **not proof of resource load success**: actual completion criteria depend on the preceding internal gates.
4. `0x122f28–0x122ff0`: if `+0xdf5 == 0`, log `Requesting Early Tubes`, build an `Initial` request with IDs 174/177 through internal calls, then set `+0xdf5 = 1`.
5. `0x122ff4–0x123330`: if `+0xdf7 == 0 && +0xdf6 != 0`, prepare the `ClusterFull` request; a **global signed counter** read at `0x123034` (pointer from literal `0x1234e8`) gates the request. If counter > 0, branch to `0x123380` and decrement at `0x123380–0x123384`; otherwise continue to the request setup at `0x12338c` (see below for separate 3D gate). The `ClusterFull` request branch sets `+0xdf7 = 1` at `0x12332c`.
6. `0x123334–0x123484`: if `+0xdf9 == 0 && +0xdf8 != 0`, log `3D Car Requested`, use `DisplayManager::getFilenameCar3D` and `DP_ID_WarnRoller_3DCar_kzbFileName`, then set `+0xdf9 = 1`.

**Correction about frame waits:** `0x123370–0x123388` is in the **3D car request gate** (`+0xdf9 == 0 && +0xdf8 != 0`), and decrements a global counter before requesting the 3D model. A separate counter/gate exists for the `ClusterFull` path at `0x123030`. Do not conflate these two stages or infer the exact frame counts without tracing the initialization of their counters.

#### State diagram (branch-backed, not timing-backed)

```text
GTF2 loading handler 0x122c54
  |
  +-- this+0xdf4 set -----------------------------> return
  |
  +-- EarlyTubes requested, not handled ---------> process EarlyTubes;
  |                                                 this+0xdf6 = 1
  +-- ClusterFull requested, not handled --------> process ClusterFull;
  |                                                 startEfsDriver();
  |                                                 this+0xdf8 = 1
  +-- EarlyTubes not requested ------------------> request Initial/EarlyTubes;
  |                                                 this+0xdf5 = 1
  +-- EarlyTubes handled, Cluster not requested -> wait/request ClusterFull;
  |                                                 this+0xdf7 = 1
  +-- Cluster handled, 3D not requested ---------> wait/request 3D car;
                                                    this+0xdf9 = 1
```

**Caveat:** The labels “requested” and “handled” follow diagnostic text and writes; the exact asynchronous callback that sets the underlying resource-ready state is still to be mapped. These flags do not by themselves prove GPU readiness or visible output.

#### Reproduce the relevant branch sites

For stripped QNX ELF, disassemble its executable `PT_LOAD` (VA `0x100000`, file offset zero) using an ARM-aware disassembler. The binary lacks a standard `.text` section header; a temporary synthetic `.text` section referencing the unchanged executable segment permits:

```sh
llvm-objdump -d --start-address=0x122c54 --stop-address=0x123490 /tmp/gtf2-with-text-section.elf
```

The synthetic-section file is a **local disassembly aid only**, never committed or distributed.

### Skin-switch preconditions and distinct KZB wait counters (ARM-confirmed)

A further pass over the **GTF2 executable itself** clarifies the first branch of `handleLoadingKZBs()`. It is **not** merely a terminal/abort flag check: `this+0xdfd` selects an in-function **skin-switch validation path**, including checks that the UI is still in the *please wait* view, no popup is active, and that the selected skin matches the requested one.

| Code VA | Evidence | Interpretation / limit |
| --- | --- | --- |
| `0x122cac–0x122cb4` | `ldrb [r4,#0xdfd]`, branch to `0x122de0` when zero | Validation path runs only when `+0xdfd != 0`; exact field name unknown |
| `0x122cb8–0x122d04` | Internal calls, diagnostic `Skin switching aborted. No longer in 'please wait' view.` | Validates view before advancing resource handling |
| `0x122d04–0x122d38` | Internal call on `this+0x20`, diagnostic `Skin switching aborted. Popup active.` | Popup presence can abort switching |
| `0x122d38–0x122dbc` | `this+0xe00` check, read config ID, compare with `this+0xdfe`; diagnostic `Skin switching aborted. MMI did not switch skin.` | Validates requested/observed skin IDs; do not invent enum values |
| `0x122dbc–0x122ddc` | Set `this+0xdf4 = 1`, invoke internal `0x69e144` and `0x121830` | Aborted/finished switching path; the earlier label “terminal/abort guard” was incomplete |
| `0x122de0` | Begins the previously mapped `EarlyTubes` completion checks | Normal resource-processing path |

**Two distinct counters**, both stored in the writable ELF segment and accessed through literal-pool addresses:

| Stage | Literal-pool slot | Global variable | Branch | Counter decrement |
| --- | --- | --- | --- | --- |
| `ClusterFull` request | `0x1234e8` | `0xa65b04` | `0x123030–0x12303c` checks positive and branches to `0x123380` | `0x123380–0x123384` |
| 3D car request | `0x1234fc` | `0xa65b08` | `0x123370–0x12337c` checks positive | `0x123380–0x123384` |

The shared decrement basic block operates on **the pointer currently held in `r3`**, so it decrements the relevant variable in either branch. `ClusterFull` logs `Done waiting -> Requesting Cluster Full` at its zero-counter path (`0x123040` onward). The 3D path logs `3D Car Requested` when its own counter has expired. Neither delay duration nor initialization site is established by these branches alone.

Literal pool also ties GTF2-owned code to precise strings: `0x1234a8` → `0x7c15c0` (please-wait abort), `0x1234ac` → `0x7c15f9` (popup abort), `0x1234b4` → `0x7c161f` (skin mismatch abort), `0x1234f0` → `0x7c1723` (ClusterFull wait completion), `0x123500` → `0x7c1760` (3D request). These are original **virtual addresses**, not file offsets.

**Remaining GTF2-only questions:** find writes/initialization for `0xa65b04` and `0xa65b08`; find the callbacks that cause `this+0xdfd` or resource state to advance; trace the internal `0x121830` transition to understand how aborted skin switching returns to the UI. No dependency-library disassembly is required.

## GTF2 frame-event dispatcher → KZB loader: reconstructed control path

This extends and **corrects** the earlier KZB-state interpretation using direct ARM disassembly of the original GTF2 `PT_LOAD`. The single statically encoded `BL` to `handleLoadingKZBs()` at `0x122c54` is **`0x12376c`**. Its enclosing GTF2-owned dispatcher starts at **`0x123520`**. The entry point is identified by the function prologue; its C++ name is not yet proven.

### Event dispatch, frame gating and render loop

| Address | ARM evidence | Consequence |
| --- | --- | --- |
| `0x123564–0x123588` | Compare event word `[r5]` with **10** or **11**; call virtual method at vtable `+0xc` on object `this+0x30` | Separate forwarding path for event kinds 10/11; exact enum labels unknown |
| `0x12358c–0x1235ac` | If event kind **9**, call `0x122498` to obtain event ID; compare with **284**; set `this+0x1ec = 1` | Explicit event-ID gate enables frame-update processing |
| `0x12363c–0x123684` | If event kind **8** and `[event+0xc] == 15`, log `switching language to %d` using `[event+0x10]`; call internal `0x1213e0` | Language-change handler |
| `0x123688–0x1236bc` | Kind **8**, subtype **6**: log `switching off render loop`, call `0x68a248` with `r1=1`, then store `this+0xdfa=1` | Render-loop disable control (semantic direction from log) |
| `0x1236c0–0x1236f4` | Kind **8**, subtype **7**: log `switching on render loop`, call `0x68a248` with `r1=0`, then store `this+0xdfa=0` | Render-loop enable control |
| `0x1236fc–0x123744` | Kind **8**, subtype **13**, `[event+0x14]` equals **0x222** or **0x221**: log `Popup was hidden`, call internal `0x121548` | Popup-hide event enters GTF2 handler |
| `0x123748–0x12376c` | Check `this+0x1ec`; if zero branch away; otherwise decrement positive `this+0xe00` and **call `handleLoadingKZBs(this)`** | Loader is invoked from frame-processing path, with a per-object countdown |
| `0x1237a0–0x1237a8` | Clear `this+0x1ec`, call internal `0x121e5c` | Frame-processing flag is reset after this path |
| `0x1237c8–0x123848` | Compare elapsed time against **500** (units depend on the surrounding clock helper); log `Frame change took %d (smudge %d)`; update timing fields `+0x1f0..+0x1fc` and global frame count | Frame performance/accounting is coupled to the same dispatcher |

The exact order in the frame branch is:

```text
GTF2 dispatcher 0x123520
  ├─ event kind 9, event ID 284 -> this+0x1ec := 1
  ├─ event kind 8, subtype 6/7 -> render loop off/on; this+0xdfa := 1/0
  ├─ event kind 8, subtype 13 + 0x221/0x222 -> popup hidden handler
  └─ if this+0x1ec != 0:
       if this+0xe00 > 0: --this+0xe00
       handleLoadingKZBs(this)                  [BL at 0x12376c]
       ... frame update and timing bookkeeping
       this+0x1ec := 0
```

**Why this matters:** the loader is not an independent, unconditionally running loop. It is reached from GTF2's own event dispatcher under a frame-processing flag, and it shares a per-object countdown with skin-switch validation.

### KZB request groups: concrete IDs and stage ordering

The KZB handler at `0x122c54` is a **single function with multiple sequential branches**, not three isolated callbacks. It uses an internal helper at `0x1217c8` with an integer resource ID in `r1`. Verified immediate values:

| Stage | Callsite(s) | IDs / behavior |
| --- | --- | --- |
| `EarlyTubes` request | `0x122f70–0x122f88` | **174**, **177**; builds `Initial` request; sets `this+0xdf5=1` at `0x122fec` |
| `ClusterFull` request | `0x123070–0x123248` | **178**, **99**, **155**, **156**, **158**, **160–166**, **168–171**, **157**, **167**, **159**, **147**, **154**; builds a request batch and conditionally adds IDs from a zero-terminated table, excluding selected IDs already handled; sets `this+0xdf7=1` at `0x12332c` |
| 3D car request | `0x1233a8–0x123480` | Calls GTF2's `DisplayManager::getFilenameCar3D` data path, constructs a filename, submits resource request through `0x141608`, sets `this+0xdf9=1` |

The `ClusterFull` batch also configures four integer options **0, 1, 6, 7** at `0x1230b4–0x1230e0`, and includes a second sequence of resource IDs from a table via `0x239a80` and the loop at `0x1232a4–0x123308`. Do not infer resource names or visual roles from numeric IDs alone.

**Important correction to earlier notes:** the byte flags `+0xdf6` and `+0xdf8` are set by **this same handler** at `0x122e5c` and `0x122eb4`, following the logged “loaded” processing branch. The code in these branches does **not** itself inspect an explicit async completion status. Therefore these flags mean **“GTF2 has executed the stage's loaded/handled branch”**, not necessarily “the underlying KZB loader has signalled completion”. Similarly, when `+0xdf9` is set, the next eligible handler pass logs `3D Car Loaded` at `0x122ed0–0x122ef8` and sets `+0xdf4=1` at `0x122efc`. This is a *terminal state of the handler*, but GPU readiness and actual successful resource loading remain unproven.

The only observed **direct** caller of `handleLoadingKZBs` is the frame dispatcher. Indirect calls cannot be excluded by a direct-BL scan.

### Counters and state: limits of current evidence

- `this+0xe00`: a **per-object** countdown decremented by the frame dispatcher at `0x123754–0x123768`, and inspected by the skin-switch validation path. It is not the same as either global KZB wait counter.
- `0xa65b04` and `0xa65b08`: **two distinct globals** gating the `ClusterFull` and 3D requests respectively, decremented through the shared basic block `0x123380–0x123384`.
- The executable text contains **one literal-pool pointer occurrence each** of `0xa65b04` (`0x1234e8`) and `0xa65b08` (`0x1234fc`). This strongly limits the directly visible access sites but does **not** prove how the globals were initialized; they could be static data or accessed indirectly.
- `this+0xdf4` is checked at entry and set on either the skin-switch abort/finalization path or after the 3D-car handled branch; calling it simply “failure” is inaccurate.
- `this+0xdfa` is distinct from KZB flags and follows the render-loop off/on events.

### Reproducible ARM disassembly

New repository script `tools/fpk1/research/gtf2/disassemble_ptload.py` builds a **temporary** ELF wrapper containing synthetic `.text` section headers pointing at the unchanged executable `PT_LOAD` bytes, invokes `llvm-objdump`, then removes the temporary copy. No firmware bytes are committed:

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py \
  /path/to/extracted/STAGE2.1/bin/gtf2 \
  --start 0x123520 --stop 0x123850

python3 tools/fpk1/research/gtf2/disassemble_ptload.py \
  /path/to/extracted/STAGE2.1/bin/gtf2 \
  --start 0x122c54 --stop 0x123490
```

This reproduces all the address-based claims above without requiring `capstone` or reverse-engineering external libraries.

**Next investigation target (GTF2 only):** track the event-ID 284 producer and the `+0x1ec` frame gate, trace `0x121548` popup-hide handling and `0x121830` skin-switch transition, and find the initialization/reset of `+0xdf4..+0xdfd`. These questions connect the loader to the UI lifecycle more directly than any OSAL implementation.

### GTF2 object initialization and skin-switch reset (additional direct evidence)

A full executable-segment scan for ARM `STRB` immediate-offset stores to `[r4,#0xdf4..0xdfd]` found a **contiguous initialization block** in the GTF2-owned function beginning near `0x122920`:

| ARM VA | Initialization |
| --- | --- |
| `0x122980` | `this+0x1ec = 0` (frame-event gate) |
| `0x1229b0` | `this+0xdf4 = 0` |
| `0x1229c8–0x1229f4` | `this+0xdf5..0xdfd = 0`, including KZB request/handled flags, render-loop flag and skin-switch flags |
| `0x1229f8` | `this+0xe00 = 0` (per-object countdown) |
| `0x1229fc` | `this+0xe08 = 0xffffffff` (sentinel; meaning TBD) |
| `0x122a00` | `this+0xe0c = 0` |

This establishes that the loader flags are **instance state initialized together**, not independent process globals. The nearby code initializes many other object members; the constructor's class name and ownership hierarchy remain to be resolved.

Another GTF2-owned routine at `0x121d80–0x121da4` explicitly **re-arms** the loading path:

- `0x121d88`: `this+0xdf4 = 0`, clearing the handler's terminal/abort gate.
- `0x121d90–0x121d9c`: transforms a signed integer input using `(x + 15) / 16` for nonnegative `x` (arithmetic right shift by 4), then writes the result to `this+0xe00` at `0x121d9c`.
- This shows the countdown is **computed** from an input parameter rather than being an arbitrary fixed literal. The input's unit and the caller remain unproven; do not label it “milliseconds” or “frames” without checking callers. For negative values the ARM adjustment differs, implementing division truncation semantics.

A separate internal routine at `0x121dbc` compares the active skin selection to an argument and clears `this+0xdfc` when equal (`0x121df8–0x121e00`), while its other path updates a skin ID and may initiate additional work. This provides an actual write site for skin-switch state outside `handleLoadingKZBs`.

The contiguous initializer, frame dispatcher and re-arm routine now form a concrete **GTF2-owned lifecycle skeleton**:

```text
instance initialization (0x122920...)
  -> frame event ID 284 sets +0x1ec
  -> dispatcher calls handleLoadingKZBs()
  -> staged requests + handled flags +0xdf5..+0xdf9
  -> 3D handled -> +0xdf4 = 1 (handler stops)
  -> separate re-arm routine clears +0xdf4 and sets +0xe00
  -> subsequent frame events can run loader again
```

This is a **possible control-flow cycle**, not proof that the re-arm routine is invoked after every completion. The next step is to resolve its callsites and the skin-switch entry points, then compare their state writes with the frame-event dispatcher.

## GTF2 skin-switch trigger and deferred dispatch (ARM control flow)

A further pass follows the **actual callsites** of the skin-switch functions, rather than inferring their purpose from string placement. The full executable-segment ARM direct-`BL` scan found:

| GTF2 callee | Direct callsite(s) | Role supported by code |
| --- | --- | --- |
| `0x121c70` | **`0x123a50` only** | Starts a skin-switch transaction, arms `this+0xdfd` |
| `0x121dbc` | `0x123a34`, `0x123de4` | Applies/compares a requested skin ID |
| `0x121548` | `0x123744`, `0x123cf8` | Handles popup-related event data |
| `0x121830` | `0x122dd8` only | Internal skin-switch completion/abort transition |
| `0x122c54` | `0x12376c` only | KZB loader called by GTF2 event dispatcher |
| `0x1213e0` | `0x123680` only | Language-change handling |

**Confirmed event-to-skin path:**

```text
GTF2 event dispatcher (0x123520), event kind 9
  -> decode event ID via 0x122498
  -> ID 500 (0x1f4) at 0x123a44
  -> BL 0x121c70 at 0x123a50
       -> this+0xdfd := 1 at 0x121cb8
       -> invoke GTF2-owned setup and view/resource-related calls
       -> clear this+0xdf4 at 0x121d88
       -> compute this+0xe00 countdown at 0x121d90..0x121d9c
  -> later frame event ID 284
       -> this+0x1ec := 1
       -> handleLoadingKZBs(this)
            -> when this+0xdfd != 0, validate please-wait view,
               popup inactivity, and selected skin
            -> staged resource handling / abort
```

**Important correction:** `0x121d80` is **not the entry point of a separate re-arm function**. It is a basic block **inside the function beginning at `0x121c70`**; the previous subsection describing it as a separate routine is superseded. Therefore the loader re-arm and countdown are **directly linked to event ID 500**, rather than merely a hypothetical post-completion reset. The function's C++ name remains unidentified; “skin-switch transaction” is a descriptive label.

The `0x121c70` path explicitly stores `this+0xdfd = 1` at `0x121cb8`, then calls internal functions `0x6a8d1c`, `0x13d098`, `0x68c34c`, `0x1418c4`, `0x13b070` and a sequence of logging/resource calls before the `0x121d88` re-arm. Its input is the object pointer `this`; the countdown is computed from a value returned by internal logic, not from an immediate event payload. Exact time units are still not established.

### Other application event IDs handled in the same GTF2 function

These values are **immediate comparisons in ARM code**, not inferred enumeration names:

| Event ID (decimal / hex) | ARM compare / branch | Observed GTF2 action |
| --- | --- | --- |
| 276 / `0x114` | `0x123938` | Calls `0x68a0dc` on `this+0x30` with argument 1 |
| 275 / `0x113` | `0x123954` | Calls `0x68a0dc` on `this+0x30` with argument 0 |
| 283 / `0x11b` | `0x123978` | Calls `0x689eac` on `this+0x30` |
| 154 / `0x09a` | `0x123994` | Calls five internal routines `0x68beec`, `0x68bd84`, `0x68bc30`, `0x68badc`, `0x68b988` on `this+0x30` |
| 519 / `0x207` | `0x1239d4` | Tree lookup in GTF2-owned structure, dispatches a 16-bit ID to `0x121dbc` |
| **500 / `0x1f4`** | **`0x123a44`** | **Calls `0x121c70`, arms skin switching** |
| 537 / `0x219` | `0x123a64` | Calls internal `0x13d098`, then `0x13ab38` |
| 547 / `0x223` | `0x123a84` | Sets **`this+0xdfb = 1`**; clears a global counter; calls popup handler `0x121548` |
| 548 / `0x224` | `0x123ad8` | Reads a global pair of counters and logs/handles them; precise effect needs more tracing |
| 289 / `0x121` | `0x123864` | Calls `0x69a418` with argument 0 |
| 271 / `0x10f` | `0x123884` | Calls `0x68db98`, then `0x692914` with argument 1 |
| 270 / `0x10e` | `0x1238a4` | Calls `0x68db98`, then `0x692914` with argument 0 |
| 291 / `0x123` | `0x1238c8` | Calls `0x12e294`, `0x12dccc`, then `0x699ca8(1)` |
| 290 / `0x122` | `0x1238ec` | Calls same pair, then `0x699ca8(0)` |
| 282 / `0x11a` | `0x123914` | Conditional calls `0x128184` and `0x128c4c` |

Do not assign symbolic names to these numeric IDs until the original event table or enum definitions are found. The comparison for ID 500 is made only in the **event-kind 9** branch (`0x12384c`), which is important for any future synthetic event injection.

### Deferred skin-ID handling at the end of dispatch

The dispatcher tests `this+0xdfc` at **`0x123cfc`**. If nonzero, it **clears that byte immediately** at `0x123d14`, performs a tree lookup keyed by event-derived data, then calls `0x121dbc` with a 16-bit skin ID at `0x123de4`. This is a distinct, deferred skin-change path from event 500. The same `0x121dbc` is also called directly after an earlier tree lookup at `0x123a34` for event 519. In `0x121dbc`, the current skin is compared with the requested ID; when equal, `this+0xdfc` is cleared at `0x121e00`.

The popup handler `0x121548` begins with a **guard on `this+0xdfb`** at `0x12154c–0x12155c`. Event 547 sets this byte before invoking the handler, so that event follows the guarded path rather than the normal event-data processing path. Exact semantics (suppression, acknowledgement or transaction state) remain unproven.

### Consolidated object state

| Object offset | Evidence-backed purpose |
| --- | --- |
| `+0x1ec` | Frame event gate, set on kind 9 / ID 284 and cleared after processing |
| `+0xdf4` | KZB handler terminal/abort gate; cleared at skin transaction start |
| `+0xdf5..+0xdf9` | Staged KZB request/handled flags |
| `+0xdfa` | Render loop on/off control |
| `+0xdfb` | Popup-handler guard, set by event 547 |
| `+0xdfc` | Deferred skin-ID processing flag, cleared by dispatcher and skin-ID comparator |
| `+0xdfd` | Skin-switch validation enabled by event 500 |
| `+0xe00` | Per-object countdown set in event-500 handler, decremented during frame processing |

This directly links **UI event dispatch, skin switching, per-frame processing, KZB loading and popup handling inside the GTF2 executable**, without inspecting any external library implementation.

### Named GTF2 functions, skin-switch handshake and DP fanout

Literal-pool resolution in the **same GTF2 ELF** adds stronger names to two previously anonymous routines:

- `0x121c70` logs **`executeSkinChange`** (string VA `0x7c12ce`, referenced via literal `0x121dac`). This is the function directly invoked by event-kind 9 / event ID 500. The same function logs **`Minimum skin change time set to %dms (can not go below %dms)`** (string VA `0x7c12e0`, literal `0x121db8`). Its input-derived `+0xe00` countdown is therefore part of a minimum skin-change timing policy. **Do not assume the integer-to-countdown conversion is real-time accurate without checking the event cadence.**
- `0x121830` logs **`switchToNewSceneGraph`** (VA `0x7c1244`, literal `0x121c44`). This function is called at `0x122dd8` on the skin-switch validation/abort path. It also contains the diagnostic **`No KSS response for skin switch`** (VA `0x7c125a`, literal `0x121c48`) and **`Skin switched`** (VA `0x7c12c0`, literal `0x121c68`). These are exact **GTF2-owned** diagnostic names, not demangled symbols.
- At `0x12185c–0x121870`, `switchToNewSceneGraph` repeatedly calls `0x10e348` on **`this+0xe04`** until its return's low byte is nonzero; at `0x1218a4–0x1218bc` it calls `0x10e09c` on the same address and tests its result. This is an explicit **blocking/polling condition** in the scene-graph switch path; the API and precise meaning of its return values are intentionally left opaque.
- The code then compares the selected skin ID at `this+0xdfe` with the value from `0x69e144(6)` at `0x1218f4–0x12190c`. The scene-graph operation is therefore coupled to GTF2's current skin selection, not merely to a generic resource-load notification.
- `0x121c20` calls `0x121498` with literal `Skin switched` before the function returns. The “skin switched” diagnostic is an *outcome of this GTF2 routine*, but its emission in a VM run is not established here.

The resulting named chain is:

```text
GTF2 event kind 9 / ID 500
  -> executeSkinChange [0x121c70]
       set +0xdfd, reset +0xdf4, configure minimum countdown +0xe00
  -> later frame events / handleLoadingKZBs [0x122c54]
       check please-wait view, popup, skin ID
       -> switchToNewSceneGraph [0x121830] on the validated/abort transition
            poll this+0xe04; check skin selection; log result
```

**Correction to earlier phrasing:** `0x121830` is not just a generic “abort transition”. It has a named scene-graph switch role and a KSS-response diagnostic. The conditions for reaching its “Skin switched” log must be read from the function's later branches; the presence of the string is not evidence of success.

#### Separate event-kind 2: DP-ID map propagation

At `0x123bbc`, the dispatcher distinguishes **event kind 2** from the kind-9 application events and the kind-8 control events. It logs/uses **`DisplayManager::dp-ID-Map`** (string VA `0x7c18da`, literal `0x123e4c`) and then iterates **exactly 180 entries**:

```text
for index = 0..179:
    if this[index + 0xd40] != 0:
        call 0x11c8ec(
            this + (index+32)*16,
            ... event-associated data ...)
```

This follows directly from the `0x123be0–0x123c0c` ARM loop: `r6` starts at zero, `ldrb [this+r6+0xd40]` tests the per-slot flag, `add r1,r6,#32` then `add r1,this,r1,lsl #4` calculates the 16-byte slot, and `cmp r6,#180` terminates the loop. **The exact semantics of `0x11c8ec` are unknown**, but the GTF2-owned fanout and data structure layout are directly supported.

After this loop, event-kind 2 compares the event payload word against several 32-bit IDs (including `0x02000114`, `0x020000be`, `0x020003f0`) and conditionally calls internal view/display routines. It may also route the payload to the popup handler `0x121548` through `0x123cf0`. These values are **not** the same namespace as kind-9 IDs 500/284; do not merge their enum labels.

This reveals **three independent event categories inside one GTF2 dispatcher**: kind 9 (application/event-ID dispatch and frame gate), kind 8 (control events), and kind 2 (DP map propagation). The event-kind labels are descriptive and must be validated against original type information.

### Exact skin-switch validation outcome: success and fallback converge

Re-examination of the `0x122d64–0x122ddc` block resolves a potentially misleading description of `switchToNewSceneGraph`. **Both** the validation-success and validation-failure paths can call it; it is not exclusively an abort handler.

1. `0x122d64–0x122d74`: read `this+0xdfe`, compare it with the skin ID returned by `0x12d208`. If different, branch into the diagnostic `Skin switching aborted. MMI did not switch skin.`.
2. If IDs match, `0x122d98` checks `r5` (set by earlier validation). If nonzero, take fallback at `0x122dbc`.
3. If `r5==0`, `0x122da0–0x122db4` tests `this+0xe00`. If **nonzero**, it returns from the loader at `0x123490` **without switching**. If **zero**, it sets `this+0xdf4=1` and falls through to `switchToNewSceneGraph` at `0x122dd8`.
4. Fallback `0x122dbc–0x122dd4` sets `this+0xdf4=1`, fetches skin ID from `0x69e144(6)` and stores it to `this+0xdfe`, then calls the **same** `switchToNewSceneGraph` at `0x122dd8`.

This proves the **minimum-countdown gate is enforced on the normal scene-graph transition**; invalid view/popup/skin checks can take a separate fallback that resets the selected ID before switching. The downstream `switchToNewSceneGraph` still has its own checks, including the `this+0xe04` polling path and the KSS-response diagnostic.

The code-supported transaction can now be summarized as:

```text
event 500 -> executeSkinChange() -> +0xdfd=1, +0xdf4=0, +0xe00=N
     |
     +-- frame 284 -> --(+0xe00) while positive
     |                -> handleLoadingKZBs()
     |                    +-- view/popup/skin mismatch -> restore selected skin
     |                    |                              +0xdf4=1
     |                    |                              switchToNewSceneGraph()
     |                    +-- valid, countdown > 0 ----> return / wait next frame
     |                    +-- valid, countdown = 0 ----> +0xdf4=1
     |                                                   switchToNewSceneGraph()
     +-- subsequent GTF2 application events continue through same dispatcher
```

**Limits:** The exact cause of `r5` being nonzero requires full register-flow analysis of the preceding checks. A zero countdown permits the scene-graph switch, but the success log and actual visual result depend on later code and runtime conditions.

## DP event fanout: 180 per-instance ordered maps, not direct widget updates

**New direct disassembly result.** Tracing the kind-2 dispatcher call `0x123c00 -> 0x11c8ec` reveals that the callee is a **map lookup / insertion helper**, not a renderer or a direct data-property update function. This corrects any earlier wording implying that the loop directly updates 180 display elements.

### Instance allocation and layout

In the GTF2 object's initializer (code around `0x122920`):

- `0x122974–0x1229a4`: loop clears four 32-bit words per iteration from **`this+0x200` through `this+0xd3f`**. The end pointer is `this+0xd40`, so this clears **2880 bytes = 180 × 16-byte slots**.
- `0x122a64–0x122a7c`: a separate loop clears exactly **180 flag bytes** at `this+0xd40..+0xdf3`. The 180 slot descriptors and 180 enable flags are contiguous, separately initialized regions.
- `0x1229b0–0x122a00`: the existing KZB/skin flags `+0xdf4..+0xdfd` and countdown `+0xe00` immediately follow these arrays. The earlier object layout was incomplete without the 180-slot region.

```text
GTF2 instance (relative to this)
  +0x0200 .. +0x0d3f   180 × 16-byte ordered-map descriptors
  +0x0d40 .. +0x0df3   180 × 1-byte enabled/active flags
  +0x0df4 .. +0x0dfd   loader, render, popup, skin-switch state
  +0x0dfe .. +0x0dff   selected skin ID (16-bit)
  +0x0e00 .. +0x0e03   skin-switch countdown
```

The exact descriptor C++ template type is not yet established; the observed callee treats each descriptor as a tree root with an element count at offset `+0xc`.

### Actual behavior of helper `0x11c8ec`

In the kind-2 event branch, the GTF2 dispatcher calls the helper once for each enabled slot:

```text
r0 = &temporary_result
r1 = this + 0x200 + (slot_index * 16)
r2 = &event_data_id  // copied from [event+4]
BL 0x11c8ec
```

Disassembly of `0x11c8ec–0x11ca04`:

1. Initializes a small output/result structure at `r0` (`0x11c8f8–0x11c908`).
2. Starts from the tree root `[r1]`, compares the incoming **32-bit event data ID** `[r2]` with each node's key at `[node+4]` and traverses children at `[node+0xc]` / `[node+0x10]` (`0x11c90c–0x11c94c`).
3. If the key already exists, returns a found result without allocating (`0x11c950–0x11c978`, `0x11c9fc`).
4. If absent, allocates **20 bytes** (`mov r0,#20; BL 0x10e7ec` at `0x11c980–0x11c984`), initializes a tree node with the event ID at offset `+4` and calls the internal insertion helper `0x116edc` at `0x11c9d4`.
5. Increments the descriptor's count at `[r1+0xc]` (`0x11c9e8–0x11c9f0`) and returns the inserted result.

The allocator and insertion routine are *called by* GTF2; their external/library internals are **not** part of this investigation. The helper itself resides in GTF2's executable segment.

**Interpretation:** an event-kind-2 message propagates its ID to all **enabled per-slot sets/maps**. This is a fanout/registration bookkeeping step. It does **not** prove that 180 widgets are rendered, that every slot is active, or that `0x11c8ec` writes a visible display property. The code after the loop separately dispatches certain data IDs to internal display-manager handlers (`0x123c18–0x123cf8`).

### Concrete DP-ID routing after fanout

Literal pool values read from the original executable:

| Dispatcher instruction | Data ID | Internal call |
| --- | --- | --- |
| `0x123c1c–0x123c34` | `0x02000110` or `0x02000111` (range compare) | `0x68beec(this+0x30)` |
| `0x123c38–0x123c4c` | `0x02000114` | `0x68bd84(this+0x30)` |
| `0x123c50–0x123c64` | `0x020000be` | `0x68bc30(this+0x30)` |
| `0x123c68–0x123c78` | `0x020003f0` | `0x68badc(this+0x30)` |

A further set of DP-ID ranges is routed to the popup-related helper `0x121548` at `0x123cf8`. The numeric IDs are original ELF constants, not inferred human-readable names.

### Reproduction

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x122974 --stop 0x122a80
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x123bc4 --stop 0x123d00
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11c8ec --stop 0x11ca08
```

**Next GTF2-only question:** locate the writes that enable `this+0xd40[index]`, and the consumers of the per-slot map contents. That will reveal whether these maps track dirty properties, subscriptions, or another form of DP state. Until then, “DP-ID registration/collection” is the narrowest supported description.

### DP slot lifecycle: enable, accumulate, flush, disable (GTF2-owned)

Following the 180-slot map **backwards to its flag writers and forwards to its consumers** resolves the previously open question. Three small GTF2-owned routines directly touch the `+0xd40` flag region:

| VA | ARM behavior | Inferred operation |
| --- | --- | --- |
| `0x120e94` | `cmp r1,#179`; if unsigned `r1 <= 179`, `strbls #1,[r0+r1+0xd40]` | **Enable slot(index)**, bounds-checked |
| `0x122338` | `cmp r2,#179`; when valid, `strb #0,[r0+r2+0xd40]` at `0x122364`, then inspect descriptor `this+0x200+16*index` | **Disable slot(index) and flush its pending IDs** |
| `0x122a64` | loop `index=0..179` storing zero at `+0xd40+index` | Initialize all slots disabled |

The function starting at **`0x122338`** does substantially more than clearing a flag:

1. Checks index `<=179`, clears its enable byte (`0x122338–0x122364`).
2. Loads the selected descriptor's node count from `this+0x20c+16*index` and its tree root from `this+0x204+16*index` (`0x12236c–0x122380`).
3. If the map is nonempty, iterates its ordered nodes (`0x122388–0x122448`), prepares an event-like record and **calls a virtual method at vtable offset `+0x4c`** on the object passed as the function's second argument (`0x1223f0–0x1223fc`). This is the GTF2-owned **flush/notification path**, not a GPU draw call.
4. Calls `0x113fd4` on the descriptor root (`0x122458–0x122460`), then clears its root, cached pointer and count (`0x122464–0x122474`).

A special constant **`0x020001cc`** is used as a sentinel/event marker while preparing flush records (literal `0x122494`). The exact consumer-side semantics of the virtual callback remain unknown.

**New important connection:** the earlier “language change” function **`0x1213e0`**, invoked from dispatcher event-kind 8 / subtype 15 at `0x123680`, also loops through all 180 active slots (`0x12140c–0x12143c`) and inserts **the same constant `0x020001cc`** into each slot's map using `0x11c8ec`. This is not merely an isolated language-setting call: it explicitly **marks every enabled slot** with a common DP-ID marker before performing its remaining GTF2-owned operations. The numeric constant should not be given a human-readable DP name without the source enum.

The resulting data-flow is:

```text
GTF2 instance constructor
  -> initialize 180 maps empty, 180 slots disabled
  -> enableSlot(index) [0x120e94, bounds <=179]
  -> DP event kind 2 [dispatcher 0x123bbc]
       -> for every enabled slot, insert event DP ID into its ordered set
  -> language event kind 8 / subtype 15 [0x1213e0]
       -> for every enabled slot, insert common marker 0x020001cc
  -> disableSlot(index, receiver) [0x122338]
       -> clear enabled flag
       -> traverse accumulated IDs, dispatch event records through receiver's
          virtual callback (+0x4c)
       -> free/reset slot map
```

**This is stronger than the previous “registration/collection” hypothesis:** GTF2 implements a **per-subscriber pending-DP-ID accumulator**, with explicit subscribe/enable and unsubscribe/flush operations. The subscriber's identity and the precise meaning of its callback are still unproven. The code shows notification on **disable**; it does not establish whether other routines flush these maps at additional times. The table does **not** represent 180 fixed visual widgets.

#### Reproduction ranges

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x120e94 --stop 0x120eb8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x1213e0 --stop 0x121494
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x122338 --stop 0x122490
```

The index is unsigned-bounded in both the enable and disable paths, avoiding out-of-bounds writes through this public interface. No external library disassembly was used.

## DP subscription owners: six concrete call paths

Scanning the original GTF2 executable's ARM `BL` instructions identifies **five direct callsites** to `enableSlot(0x120e94)` and **three** to `disableAndFlushSlot(0x122338)`. This connects the per-slot accumulator to **caller-owned subscription lifecycle**, not to a single global render-loop update.

| Operation | Direct caller VA | Evidence from surrounding ARM instructions |
| --- | --- | --- |
| enable | `0x119870` | Caller loads slot index from `[r4+0x1c]` into `r1`; the object pointer `r0` is returned by immediately preceding helper `0x113e50`; follows with `0x12a77c` and `0x12a348` |
| enable | `0x119bb0` | Same slot index field `[r4+0x1c]`, same helper `0x113e50`; sets up separate caller-local state |
| enable | `0x11a710` | Same slot index field `[r4+0x1c]`, same helper `0x113e50`; different surrounding caller path |
| enable | `0x6a9298` | Same index field `[r4+0x1c]`, helper `0x113e50`, then virtual method at vtable `+0x54` |
| enable | `0x6a9174` | Fifth direct callsite in same `0x6a91xx` region; inspect full enclosing function for its preconditions |
| disable/flush | `0x119d1c` | `r1=[r4+0x18]` (receiver), `r2=[r4+0x1c]` (slot index), `r0` from `0x113e50`; after flush invokes `0x6a9e9c` and `0x117c40` |
| disable/flush | `0x11a588` | Same receiver/index fields and helper; after flush invokes `0x6a9e9c` and `0x117c40` |
| disable/flush | `0x6a92f0` | Same receiver/index fields and helper; then invokes receiver's virtual method at vtable `+0x28` |

The repeated `[caller+0x18]` / `[caller+0x1c]` layout is **strong evidence for a shared subscriber object convention**: one field is the notification receiver, the other the integer slot ID. The `0x113e50` helper provides the GTF2 manager object on which the slot functions operate. Its internal implementation is not needed to follow this caller-level contract.

**Important boundary:** these caller objects reside in GTF2's own executable, but their exact C++ class names and relationship to `ViewManager` remain unproven. The evidence supports subscriber/receiver ownership, **not** a claim that each callsite is a distinct screen or that the receiver is necessarily a view.

### Confirmed callback interface

The disable/flush routine `0x122338` dispatches each pending ID by loading the receiver's vtable and calling its entry at **`+0x4c`** (`0x1223f0–0x1223fc`). That is a **virtual callback interface** into the caller-supplied receiver. The receiver is passed explicitly in `r1`; no global rendering API is invoked by the flush routine.

The caller at `0x6a92f0` then invokes a **different** receiver virtual entry at `+0x28` (`0x6a92f4–0x6a930c`), consistent with a separate post-unsubscribe lifecycle action. The exact interface method names remain unknown.

### Full direct-caller inventory for insertion helper

The GTF2-local ordered-map insertion helper `0x11c8ec` has **12** direct ARM `BL` callsites:

`0x11d7a8`, `0x11db48`, `0x11efd4`, `0x121430`, `0x123c00`, `0x1ab00c`, `0x1ab040`, `0x6a4874`, `0x6a49b8`, `0x6a4b38`, `0x6a5080`, `0x6a5148`.

This is the direct-call inventory; other indirect callers are possible. The presence of insertion calls outside the event dispatcher and language-change handler means the ordered-map helper is reused in other GTF2-owned structures; not every call to `0x11c8ec` necessarily targets the 180-slot array. Its semantics are a generic map insertion, and the *caller-provided descriptor* determines the map.

### Reproduction

```sh
python3 tools/fpk1/research/gtf2/scan_dp_slot_calls.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x119b70 --stop 0x119bd0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x119ce0 --stop 0x119d40
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a9284 --stop 0x6a9318
```

**Next GTF2-only task:** resolve vtable(s) of the receiver object passed as `[caller+0x18]`, and locate the implementations at offsets `+0x4c` and `+0x28`. This should identify how pending DP-ID notifications are consumed without analyzing external libraries.

## View switching owns DP subscription lifecycle: BaseViewManager

**Direct ELF diagnostic and ARM control-flow cross-reference.** The previously unnamed GTF2 routine at **`0x6a91a8`** is anchored by literal-pool strings `BaseViewManager::handleViewSwitch` (pool VA `0x6a9324` → string VA `0x891bbe`), `handleViewSwitch` (`0x6a932c` → `0x891bcf`) and `handleViewSwitch: %p` (`0x6a9330` → `0x891be0`). This **links the 180-slot DP subscription API directly to a GTF2 view-manager operation**, rather than to a generic subscriber of unknown provenance.

### Verified state transitions in `handleViewSwitch`

The function `0x6a91a8–0x6a9320` accepts `r0=this`, `r1` and `r2` as arguments. Its ARM instructions show:

1. `0x6a91dc–0x6a91ec`: invoke `this` virtual method **`+0x58`** with the third input (`r2`), retaining the returned value in `r6`. Compare it against **`this+0x18`** (`0x6a91f0–0x6a91fc`).
2. If the returned value is null, branch toward `0x6a9310` and clear **`this+0x22`**. If unchanged and `+0x22==0`, return early at `0x6a9318`.
3. For a changed non-null target, when the **old `this+0x18` is non-null**, call its virtual methods **`+0x2c`** and **`+0x30`** (`0x6a9244–0x6a9280`), then call **`enableSlot` at `0x6a9298`** using the old `this+0x1c` slot index.
4. `0x6a929c–0x6a92b4`: update the active-view state: **`this+0x18 := r6`** (new view), **`this+0x1c := [r7]`** (new slot ID supplied indirectly by the caller).
5. `0x6a92b8–0x6a92dc`: invoke virtual method **`+0x54`** on `this` and **`+0x24`** on the new active-view object.
6. `0x6a92e0–0x6a92f0`: call **`disableAndFlushSlot(0x122338)`** with `r1=this+0x18` (the **new** active-view pointer) and `r2=this+0x1c` (the **new** slot ID).
7. `0x6a92f4–0x6a930c`: invoke the new view's virtual method **`+0x28`**. Return.

**Crucial ordering correction:** earlier documentation described `+0x18` as a “receiver” and `+0x1c` as a slot ID, which remains correct for this object layout. But the view-switch routine changes both fields **before** calling `disableAndFlushSlot`. Therefore the flush is passed the **new view and new slot ID**, not the old view. Do not infer a simple “unsubscribe old view, subscribe new view” pattern from the helper names alone. The seemingly counterintuitive order may implement a view-switch notification handshake or slot ownership transfer; exact semantics require inspecting the vtable implementations.

The `enableSlot` call at `0x6a9298` occurs on the **old** slot before the new-view fields are assigned. It may preserve pending changes during transition, rather than merely subscribe a new view. The ARM ordering is stronger evidence than conventional method naming.

### Other confirmed ViewManager anchors

A separate GTF2 function around `0x119800` contains direct diagnostics:

- `0x119a48` literal → `0x7bf437`: **`doSwitch(), switching off current view %s before delay for context fade in for popup`**.
- `0x119a58` literal → `0x7bf41f`: **`ViewManager::justHidden`**.

At `0x119870` it calls `enableSlot` with `[this+0x1c]`; at `0x119890–0x11989c` it clears `this+0x18` and `this+0x1c`. This is another concrete point where view transitions affect the DP slot lifecycle.

### Architecture consequence

```text
GTF2 kind-2 DP event
  -> for every active DP slot, accumulate DP ID in ordered set
GTF2 BaseViewManager::handleViewSwitch [0x6a91a8]
  -> query requested view via virtual +0x58
  -> call outgoing view virtual methods
  -> enable old DP slot
  -> assign new view pointer and slot ID
  -> invoke new view lifecycle methods
  -> flush new slot's pending DP IDs via receiver virtual +0x4c
  -> invoke new view virtual +0x28
ViewManager::doSwitch / justHidden [~0x119800]
  -> another view-transition path enabling and resetting slot state
```

**Caveats:** the `+0x4c` callback is virtual, so the concrete target varies by view class. The mapping from the 180 numeric slot IDs to actual view names is still unknown. This evidence demonstrates a **direct architectural coupling between DP accumulation and GTF2 view transitions**, not a completed mapping of every dashboard widget.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/inspect_view_switch.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a91a8 --stop 0x6a9324
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x119800 --stop 0x1198b8
```

No external library implementations were analyzed.

## BaseViewManager vtable recovered from actual constructor writes

The GTF2 ELF contains a **concrete virtual-function table at VA `0x891958`**. This is not a guessed C++ layout: multiple GTF2-owned routines load this exact pointer from literal pools and write it into `[this]`.

**Direct constructor/vptr evidence:**

- `0x117a34–0x117a7c`: constructor-like routine initializes members and writes `0x891958` into `[this]` at **`0x117a6c`** (literal `0x117a84`).
- `0x117a88–0x117acc`: a second constructor-like routine writes the same vptr at **`0x117abc`** (literal `0x117ad0`).
- `0x6a8d24–0x6a8d2c`: tiny vptr-reset function stores the same pointer; literal `0x6a8d30`.
- `0x6a8d3c–0x6a8d54`: destructor-like routine writes the vptr and calls a cleanup helper; literal `0x6a8d58`.
- `0x11ad68` is another exact literal reference to the table, not yet attributed to a constructor.

**All 21 table entries, directly read from the original ELF** (addresses relative to vptr `0x891958`):

| Slot | GTF2 function | Slot | GTF2 function |
| --- | --- | --- | --- |
| `+0x00` | `0x6a8d24` | `+0x04` | `0x6a8d3c` |
| `+0x08` | `0x6a8d34` | `+0x0c` | `0x117398` |
| `+0x10` | `0x1173a8` | `+0x14` | `0x1173bc` |
| `+0x18` | `0x1173cc` | `+0x1c` | `0x6a9008` |
| `+0x20` | `0x6a8f80` | `+0x24` | `0x6a8f14` |
| `+0x28` | `0x6a8e84` | `+0x2c` | `0x6a96d0` |
| `+0x30` | `0x6a9468` | `+0x34` | `0x6a93e0` |
| `+0x38` | `0x6a94f4` | `+0x3c` | `0x6a8dac` |
| `+0x40` | `0x6a9064` | `+0x44` | `0x1179dc` |
| `+0x48` | `0x6a9334` | `+0x4c` | `0x1173d4` |
| **`+0x50`** | **`0x6a91a8`** | | |

The `+0x50` entry is the previously identified `BaseViewManager::handleViewSwitch` implementation. This **confirms its virtual slot**, which is valuable for locating callsites that dispatch through `[vptr+0x50]` without a direct ARM `BL`.

**Other decoded entries:**

- `+0x08 -> 0x6a8d34`: returns `this+0x1c` (the view/slot identifier).
- `+0x18 -> 0x1173cc`: returns byte `this+0x24`.
- `+0x4c -> 0x1173d4`: returns byte `this+0x23`. This is a trivial getter **for BaseViewManager objects**, **not** the per-view notification callback seen in `disableAndFlushSlot`. That callback is invoked through the *view receiver's own vtable*, whose concrete type may differ.
- The table ends after `+0x50` (the following word `0x8919ac` is zero), followed by other ELF data and diagnostics.

**Caution on class identification:** the strings `BaseViewManager::handleViewSwitch` and `handleViewSwitch` prove the diagnostic context of `0x6a91a8`; constructor vptr stores prove the table belongs to the same GTF2 object family. Whether derived view-manager classes replace this vptr with their own table at runtime is still to be determined. Do not treat all virtual dispatch as necessarily targeting this base table.

### Reproducible vtable extraction

```sh
python3 tools/fpk1/research/gtf2/inspect_vtable.py /path/to/gtf2 \
  --vtable 0x891958 --entries 21

python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 \
  --start 0x117a34 --stop 0x117ad4

python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 \
  --start 0x6a8d24 --stop 0x6a8d5c
```

**Next GTF2-only analysis:** find vtables for the **view receiver** objects passed to `disableAndFlushSlot`, then map their `+0x4c` implementations and the manager's `+0x58` virtual view lookup. The latter is **not** an entry in this 21-entry base table, suggesting that a derived table or different manager object is involved. The code evidence above resolves the base table, not yet all derived classes.

## Derived ViewManager vtable found: resolves missing virtual +0x58

**Verified against original GTF2 ELF bytes in this pass.** The previously unresolved virtual slot `+0x58` is present in a **larger, related vtable at `0x7bfaf0`**, not in the 21-entry base table at `0x891958`. This resolves the major gap in the last section.

The related table has **25 function entries**, ending at `+0x60`, followed by zero at `0x7bfb54`. The first 21 entries share many methods with the base table, while several are overridden. Crucially, its first entries include `0x117a88` and `0x117a34` (the constructor-like functions discussed above). **Literal pointers to `0x7bfaf0`** occur at `0x117a80`, `0x117acc` and `0x11ad6c`, adjacent to pointers to the base table at `0x117a84`, `0x117ad0`, `0x11ad68`. These exact pairings are strong evidence of **related base/derived object setup**. Precise source class names for the larger table are not yet proven.

### Side-by-side virtual method slots

| Offset | Base `0x891958` | Extended `0x7bfaf0` |
| --- | --- | --- |
| `+0x00` | `0x6a8d24` | `0x117a88` |
| `+0x04` | `0x6a8d3c` | `0x117a34` |
| `+0x08` | `0x6a8d34` | `0x1173dc` |
| `+0x0c..+0x28` | same implementations | same implementations |
| `+0x2c` | `0x6a96d0` | `0x11a8bc` |
| `+0x30` | `0x6a9468` | `0x6a9468` |
| `+0x34` | `0x6a93e0` | `0x6a93e0` |
| `+0x38` | `0x6a94f4` | `0x11a880` |
| `+0x3c` | `0x6a8dac` | `0x118544` |
| `+0x40` | `0x6a9064` | `0x118354` |
| `+0x44` | `0x1179dc` | `0x1179dc` |
| `+0x48` | `0x6a9334` | `0x6a9334` |
| `+0x4c` | `0x1173d4` | `0x1173d4` |
| **`+0x50`** | **`0x6a91a8`** | **`0x11a250`** |
| `+0x54` | absent | `0x11a864` |
| **`+0x58`** | **absent** | **`0x11871c`** |
| `+0x5c` | absent | `0x118c74` |
| `+0x60` | absent | `0x119688` |

**Key architectural correction:** `0x6a91a8` is the **base-class** implementation of `handleViewSwitch` (base slot `+0x50`), whereas the extended vtable **overrides the same slot with `0x11a250`**. The code at `0x11a250` has a substantial body and its own state-machine branches. Therefore tracing only `0x6a91a8` is insufficient to reconstruct the actual switching behavior of the extended manager. The previous subsection's old/new slot ordering remains valid **for the base implementation only**; it must not be generalized to the derived path.

### Exact behavior of derived `+0x58 -> 0x11871c`

Disassembly of `0x11871c–0x11874c` shows a compact decision:

```text
virtual +0x58(this, output_slot_id)
  if this+0x25 != 0 OR this+0x26 != 0:
      *output_slot_id = this+0x1c
      return 0x6a9e9c(this+0x1c)
  else:
      return 0x6a8d5c(this, output_slot_id)
```

The branch to `0x6a9e9c` uses a **global provider object** loaded from `0xdb1900`, tests it for null, and then dispatches its virtual method at `+0x00` with the requested slot ID. The global provider's concrete type and the returned view object's class are not yet proven. The other branch `0x6a8d5c` is an inherited/base lookup path.

**Consequence:** the virtual lookup invoked by `BaseViewManager::handleViewSwitch` at `0x6a91e8` is concretely implemented in the extended manager. It chooses between an active/current slot lookup and the inherited lookup according to **two instance flags** `+0x25` and `+0x26`. This establishes a meaningful part of the **view selection policy**, rather than merely identifying a vtable pointer.

### Next investigation target

1. Disassemble **`0x11a250–0x11a828`** as the **derived `handleViewSwitch` override**; trace flags `+0x25`, `+0x26`, `+0x54`, `+0x88` and virtual callbacks. This should supersede any assumption that the base handler is always active.
2. Follow `0x6a8d5c` and the provider at `0xdb1900` to map numeric slot IDs to view objects.
3. Identify concrete view receiver vtables (their `+0x4c` handlers) using constructor vptr stores.

### Reproduce directly from original ELF

```sh
python3 tools/fpk1/research/gtf2/inspect_vtable.py /path/to/gtf2 --vtable 0x7bfaf0 --entries 25
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11871c --stop 0x118750
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11a250 --stop 0x11a828
```

These results use the GTF2 ELF itself; no shared libraries or proprietary firmware bytes are committed.

## Derived ViewManager::handleViewSwitch — delayed transition state machine

Direct disassembly of **`0x11a250–0x11a828`** in the original GTF2 ELF establishes the **derived** view switch handler. The diagnostic literal `0x11a830 -> 0x891bc2` is **`ViewManager::handleViewSwitch`** (as opposed to the base handler's `BaseViewManager::handleViewSwitch`). The routine contains several independently gated transition paths, not just a single base-method delegation.

### Entry gates and time comparisons

- `0x11a2a0–0x11a2b8`: check two byte flags **`this+0x25`** and **`this+0x26`**. If *both zero*, branch to **`0x11a800`**, which directly invokes base **`0x6a91a8`** at `0x11a80c`, then calls `0x119614`. This proves that the derived manager **retains the base transition path** in its ordinary/no-special-mode case.
- If either flag is nonzero, check **`this+0x88`** at `0x11a2b8`. When nonzero, compare a timestamp against a **1000-unit** offset (`0x11a2c4–0x11a2f8`), log **`handleViewSwitch(isPopup=%d), needle sweep active, suppressing all view changes`**, store timestamp words at **`this+0x80/+0x84`**, then exit. The code strongly supports a **needle-sweep suppression gate**; the time unit of the 64-bit clock is not proven solely by the immediate 1000.
- `0x11a32c–0x11a43c`: when **`this+0x25`** and **`this+0x54`** are nonzero, compare a 64-bit deadline at **`this+0x50`** against a clock plus **200** (`0x11a350–0x11a37c`). A target change updates **`this+0x3c`** and **`this+0x58`**, and caches a 64-bit time at **`this+0x60/+0x64`** (`0x11a37c–0x11a3ec`). A further clock comparison uses **1000** and may log **`handleViewSwitch, waiting for end of delay`** (`0x11a3f0–0x11a43c`).
- `0x11a440–0x11a464`: when the delay branch is not taken, compare the current target with the cached **`this+0x3c`** and set **`this+0x54=1`** if the target differs.

### Deferred view-switch cancellation and notification

- `0x11a468–0x11a4c0`: build a temporary event/result record. If **`this+0x26`** is nonzero, call internal **`0x118878`** to prepare additional state. Then query manager helper **`0x1224b8`**, storing the result in `r10`.
- `0x11a4d8–0x11a5fc`: if **`this+0x25`** and **`this+0x71`** are set, compare the target against **`this+0x1c`**. When equal, log **`delayed view switch canceled, sending view %s aboutToShow`**, call current view's **virtual `+0x24`** (`0x11a544–0x11a574`), then **disable/flush its DP slot** through `0x122338` at `0x11a588`. The handler also calls GTF2-owned helpers `0x117c40`, `0x11de04`, and `0x120048`. The diagnostic **`delayed view switch canceled, fading in %s`** belongs to the alternate branch where the target differs (`0x11a5c4–0x11a5f8`), which sets **`this+0x40=1`** and clears **`this+0x54`**.
- `0x11a610–0x11a634`: if special-mode processing proceeds, clear **`this+0x70`** and **`this+0x71`**, then call the derived manager's virtual **`+0x5c`** (vtable `0x7bfaf0` maps this to **`0x118c74`**). This is a concrete virtual transition hook absent from the base table.

### Deferred transition launch

- `0x11a638–0x11a674`: verify requested target differs from current **`this+0x1c`**, current view pointer **`this+0x18`** is nonnull, and `this+0x71` is zero.
- If **`this+0x70`** is set, `0x11a678–0x11a738` clears it, logs **`delayed view switch to %s, sending view %s justHidden`**, invokes current view's virtual **`+0x30`** (`0x11a6d0–0x11a6f8`), calls **`enableSlot`** at `0x11a710`, sets **`this+0x71=1`** and resets **`this+0x68=0`**.
- Otherwise `0x11a73c–0x11a7dc` logs **`trying to trigger delayed view switch to %s from %s`**, constructs two temporary state records via `0x118750`, and invokes GTF2-owned **`0x11cbb0`** with a function pointer literal **`0x117fd4`** and `this`. This is a **callback-driven delayed transition request**; the exact callback's effects require separate analysis.

### Source-anchored diagnostic strings

| Literal pool VA | String VA | Exact GTF2 diagnostic |
| --- | --- | --- |
| `0x11a830` | `0x891bc2` | `ViewManager::handleViewSwitch` |
| `0x11a834` | `0x7bf63c` | `handleViewSwitch(viewID=%d, viewName=%s)` |
| `0x11a83c` | `0x7bf665` | `handleViewSwitch(isPopup=%d), needle sweep active, suppressing all view changes` |
| `0x11a840` | `0x7bf6b5` | `handleViewSwitch, target changed within delay time, reset delay timer for %s` |
| `0x11a844` | `0x7bf702` | `handleViewSwitch, waiting for end of delay` |
| `0x11a848` | `0x7bf72d` | `handleViewSwitch(), delayed view switch canceled, sending view %s aboutToShow` |
| `0x11a850` | `0x7bf796` | `handleViewSwitch(), delayed view switch canceled, fading in %s` |
| `0x11a854` | `0x7bf7d5` | `handleViewSwitch(), delayed view switch to %s, sending view %s justHidden` |
| `0x11a85c` | `0x7bf839` | `handleViewSwitch(), trying to trigger delayed view switch to %s from %s` |

### Reconstructed high-level state model

```text
derived ViewManager::handleViewSwitch
  if !flag25 && !flag26:
      BaseViewManager::handleViewSwitch()
      additional derived follow-up
  else if needle_sweep_flag88:
      suppress view change, update timestamp
  else:
      compare target/deadline, maybe wait and cache target
      inspect pending delayed-switch state
      if delayed switch canceled:
          notify current view (+0x24), flush DP IDs
          or mark fade-in/reset pending flag
      else if special transition needs continuation:
          invoke virtual manager +0x5c
      else if current view exists and target differs:
          if pending justHidden flag70:
              notify current view (+0x30)
              enable old DP slot; set flag71
          else:
              schedule callback-driven delayed switch via 0x11cbb0
```

This is **not a claim of exact source-level control-flow equivalence**: branch names are derived from diagnostic strings and observed state writes, and the callback at `0x117fd4` still needs decoding. However, the key conclusion is robust: the derived ViewManager contains an **asynchronous/delayed view-transition state machine** that the base `0x6a91a8` handler alone does not describe.

**Next GTF2-owned targets:** callback `0x117fd4`, virtual manager `+0x5c -> 0x118c74`, and derived `+0x60 -> 0x119688`. Together they should clarify the scheduling, cancellation, and completion of view transitions.

### Deferred callback resolved: `0x117fd4` arms the `justHidden` transition

The function pointer `0x117fd4` passed to GTF2-owned scheduler `0x11cbb0` at `0x11a7d4` resolves to a **tiny GTF2 callback**:

```text
0x117fd4:
    log diagnostic (when log level permits)
    if callback_this == NULL: invoke failure/assert helper
    callback_this->byte_0x70 = 1  [STRB at 0x118028]
    return
```

This closes an actual state-machine loop, not merely a suggestive log string:

1. Derived `ViewManager::handleViewSwitch` at `0x11a7d4` schedules callback **`0x117fd4`** through `0x11cbb0`.
2. When invoked with a valid manager pointer, the callback sets **`this+0x70=1`**.
3. A later `handleViewSwitch` call checks **`this+0x70`** at `0x11a66c–0x11a674`.
4. The armed branch **clears `+0x70`** at `0x11a67c`, calls the current view's virtual **`+0x30`** (the diagnostic labels this `justHidden`), enables its DP slot via `0x120e94`, sets **`this+0x71=1`** and resets **`this+0x68=0`** (`0x11a700–0x11a730`).

```text
delayed view switch requested
  -> schedule callback 0x117fd4
       -> manager.flag70 = 1
  -> next eligible ViewManager::handleViewSwitch
       -> manager.flag70 = 0
       -> outgoing_view.virtual(+0x30)
       -> enable DP slot
       -> manager.flag71 = 1
       -> manager+0x68 = 0
  -> subsequent delayed/cancellation branches observe flag71
```

This **proves a two-stage delayed view transition handshake**: a scheduled callback signals readiness by writing `+0x70`, and the view manager consumes the signal in a subsequent dispatch. It does **not** establish the callback's wall-clock delay, scheduler threading model, or the exact meaning of the receiver's virtual method beyond the diagnostic label.

The next extended virtual method **`+0x5c -> 0x118c74`** is a larger state-machine routine. Its entry (`0x118cc4–0x118d44`) checks **`+0x40`**, **`+0x25`** and a cached target at **`+0x3c`**; on a target change it updates `+0x3c`, then dispatches the derived virtual **`+0x60`**. Another branch (`0x118d48–0x118d64`) consumes **`+0x48`** by clearing it before further view processing. This links the derived virtual hooks to the same target/cancellation flags, but their full semantics require continued analysis.

Reproduce:

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x117fd4 --stop 0x118044
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x118c74 --stop 0x118d70
```

## Derived virtual +0x5c is `ViewManager::handleViewSwitchCenter`

The previously unnamed extended-manager virtual slot **`+0x5c -> 0x118c74`** has a definitive diagnostic name in the original GTF2 ELF: **`ViewManager::handleViewSwitchCenter`**, at string VA `0x7befeb` (literal pool `0x1195c0`). The function occupies **`0x118c74..0x1195b4`**, substantially larger than the initial entry block. This is the **center/popup-aware transition coordinator** invoked from the derived `handleViewSwitch` at `0x11a634`.

### Concrete code evidence

- `0x118c74`: saves nine ARM registers and reserves **212 bytes** of stack, consistent with a substantial transition routine rather than a simple view lookup.
- `0x118cc4–0x118d44`: when **`this+0x40`** is set, and **`this+0x25`** is nonzero, compare requested target `[r5]` against cached target **`this+0x3c`**. A different nonzero target updates `+0x3c`; the function then invokes **derived virtual `+0x60`** (table `0x7bfaf0` → `0x119688`). Diagnostic: **`target changed while we were fading out from %s to %s`**.
- `0x118d48–0x118e10`: consume pending **`this+0x48`** by clearing it. If a current view exists and `this+0x44 == this+0x1c`, send **virtual `+0x28`** to the current view with a four-byte all-ones temporary flag array; update **`this+0x44 = 181`**, then branch to either `0x117e58` or `0x117dcc` based on **`this+0x26`**. Diagnostic: **`faded in`**. This is a separate **fade-in completion** branch.
- `0x118e24–0x118e60`: **`this+0x49`** can force requested view ID **181**; otherwise the code validates a candidate against an upper bound **179** and a provider result from `0x6a9e9c`. This proves the transition coordinator uses **special IDs beyond the 180 DP slot indices**; view IDs and DP slot indices must not be assumed interchangeable in every branch.
- `0x118e88–0x118f44`: when cached target `this+0x3c` is nonzero and differs from requested target, log **`changing target view`**, update the cached target, and inspect a 64-bit timestamp **`this+0x60/+0x64`**. A nonexpired deadline logs **`reset delay timer`** and updates `this+0x58`.
- `0x118f6c–0x1190fc`: on a new target, log **`starting view change from %s to %s (center %d, popup %d)`**, call `0x11de04`, inspect view object properties via GTF2 functions `0x146320` and `0x146200`, and use helper **`0x1189a0`** to compare center-related state. It selects a transition code **25**, **2**, or **8** at `0x1190e4–0x1190fc`, depending on these comparisons and `this+0x26`. These are *internal transition codes*, not verified UI event IDs.

### Diagnostic names for the rest of this routine

The original ELF also includes these exact `handleViewSwitchCenter` diagnostics, referenced in the `0x1195bc..0x119610` literal pool:

- `instant view change active, no animation!`
- `starting fade out animation 1`
- `no fade out necessary`
- `partial popup waiting for fade out of popup glass plate`
- `switching from popup to popup`
- `starting fade out animation 2`
- `starting fade out animation 3`

These establish that **normal view changes, popup-to-popup transitions, partial-popup transitions, and instant/no-animation paths are handled in one GTF2-owned coordinator**. The precise animation event/callback completion paths must be resolved from the remaining `0x119100..0x1195b4` branches before assigning exact timing or completion guarantees.

### Corrected view-ID distinction

The earlier DP-slot enable/disable APIs bound their indices to **0..179**. The center coordinator explicitly uses **181** as a special requested/transition view ID (`0x118db0`, `0x118e2c`), and compares other values against 179. Therefore the 180 DP slots are **not a complete enumeration of every view-related state**. A special ID can represent a transitional state or sentinel; its exact symbolic meaning remains unknown.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x118c74 --stop 0x1195b8
python3 tools/fpk1/research/gtf2/inspect_vtable.py /path/to/gtf2 --vtable 0x7bfaf0 --entries 25
```

**Next GTF2-only work:** decode `0x119100..0x1195b4` (animation launch paths), `+0x60 -> 0x119688` (derived completion/cancellation), and the helper `0x1189a0` (center selection). This should connect the fade-out callbacks to the already proven `+0x70/+0x71` delayed-switch handshake.

### Animation launch and derived completion hook `+0x60`

The remaining half of `handleViewSwitchCenter` and the entry of the derived virtual **`+0x60 -> 0x119688`** were inspected directly.

**Animation launch paths in `handleViewSwitchCenter`:**

- `0x1193a8–0x1193e0`: constructs three temporary animation/state descriptors with immediate **2**, **8** and **4**, using GTF2-owned helper **`0x118750`**.
- `0x1193e4–0x119438`: depending on a temporary flag at `[sp+0xa4]`, logs **`instant view change active, no animation!`** and calls **`0x11f414`** with argument `4`. The branch uses an internal GTF2 scheduling/animation entry point; its runtime effect is not proven solely by the log.
- `0x11943c–0x119478`: the other branch logs **`starting fade out animation 2`** and calls **`0x11f794`** with argument `4`.
- `0x119480–0x1194f4`: in a popup-specific branch (`this+0x26` and temporary flag set), logs **`instant view change active, no animation!`** and calls **`0x11f414`** with argument `6`.
- `0x119500–0x119540`: alternate branch logs **`starting fade out animation 3`** and calls **`0x11f930`** with argument `6`.
- `0x119544–0x119574`: if the old view exists, invokes its **virtual `+0x2c`** with a four-byte temporary array whose bytes are all **1**. Then chooses `0x117e58` versus `0x117dcc` based on **`this+0x26`** (`0x119578–0x1195a8`). This links animation launch to a subsequent view-lifecycle notification.
- `0x1195ac`: common post-transition helper **`0x118b78`**.

**Derived virtual `+0x60` at `0x119688`:**

- Entry diagnostic strings are located in the literal pool `0x119a38..0x119a44`; this is a **separate** manager virtual hook, not a continuation of the center coordinator.
- `0x1196d4–0x119724`: when **`this+0x26`** and **`this+0x49`** are set, and cached target **`this+0x3c != 181`**, explicitly **overwrites `this+0x3c = 181`**. Thus **181 is an active transition target sentinel**, not merely a one-off invalid input value.
- `0x119728–0x119784`: if **`this+0x54`** is set and the target differs from cached **`this+0x58`**, update `+0x58` and a floating-point timing field at `+0x60`, then branch to common tail `0x11a240`. This links the derived completion/continuation hook to the delay-timer fields used by `handleViewSwitch`.
- `0x11978c–0x1197d0`: a further special branch requires **`+0x40 != 0`**, **`+0x26 != 0`**, **`+0x18 != NULL`**, **`+0x78 == +0x7c == 0`**, and **`+0x49 != 0`**. It then inspects the current view via **`0x146320`**. These are concrete, multi-field gating conditions; naming this branch “completed” without further analysis would be premature.

**Important architecture conclusion:** the derived ViewManager splits switching into at least three GTF2-owned layers:

```text
virtual +0x50  ViewManager::handleViewSwitch [0x11a250]
  ├─ normal/base transition -> BaseViewManager::handleViewSwitch
  ├─ delayed callback handshake (+0x70 -> +0x71)
  └─ virtual +0x5c  handleViewSwitchCenter [0x118c74]
       ├─ center/popup target selection and sentinel 181
       ├─ animation launch (0x11f414 / 0x11f794 / 0x11f930)
       └─ virtual +0x60 [0x119688]
            ├─ special target override to 181
            ├─ delayed-target/timer state updates
            └─ additional view-specific gated transitions
```

The code distinguishes **“instant/no-animation”**, **fade-out animation 2/3**, and **popup-dependent transitions**. It does not yet establish which screen IDs correspond to named dashboard screens, or whether a particular animation completes under QEMU.

Reproduction:

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x1193a8 --stop 0x1195b8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x119688 --stop 0x119800
```

## Names resolved: virtual +0x60 is `ViewManager::doSwitch`; `0x1189a0` selects display contexts

A new direct inspection of the original GTF2 ELF resolves the previously anonymous derived virtual slot **`+0x60 -> 0x119688`**. Its own literal pool at `0x119a38–0x119a4c` points to these exact diagnostic strings:

| Literal VA | String VA | Diagnostic |
| --- | --- | --- |
| `0x119a38` | `0x7bf343` | `doSwitch(popup=%d), changing view to %s` |
| `0x119a3c` | `0x7bf36b` | `doSwitch, we have faded out and were about to fade in, but we got the request to fade out again. Attempted to fade in %s` |
| `0x119a40` | `0x7bf3e4` | `doSwitch, setting delay timer for %s (delayCenterStage %d)` |
| `0x119a48` | `0x7bf437` | `doSwitch(), switching off current view %s before delay for context fade in for popup` |
| `0x119a4c` | `0x7bf48c` | `doSwitch(), waiting before fading in context` |

Thus the slot is specifically **`ViewManager::doSwitch`** (diagnostic attribution), rather than a generic “completion” hook. Its already-established branches for `this+0x49`, `this+0x54`, cached target `this+0x3c`, and sentinel **181** must be interpreted in the context of **starting/redirecting an animated switch**, not merely completing one.

### `contextIdFromView` helper at `0x1189a0`

This helper is called during the center/popup transition and is identifiable from its diagnostic pool:

- `0x118b64 -> 0x7beec3`: **`contextIdFromView()`**
- `0x118b6c -> 0x7beed7`: **`Failed to find display context where context->isVisible() evaluates to true`**
- `0x118b70 -> 0x7bef23`: **`Sending context id of first usable display context`**
- `0x118b74 -> 0x7bef56`: further failure diagnostic (see original ELF).

Verified disassembly behavior:

1. `0x1189d8–0x1189e8`: initialize two 16-bit output context IDs to **-1** and a separate output flag to **0**.
2. `0x1189f0–0x118a14`: invoke input view object's **virtual `+0x54`** to obtain a collection of display contexts. This `+0x54` belongs to the **view object**, not to the manager's vtable.
3. `0x118a1c–0x118a94`: iterate context pointers. Each non-null context is queried via its own **virtual `+0x00`**; a non-null result is tested by GTF2 function `0x1355f8`.
4. `0x118a50–0x118a84`: for the selected visible context, use its **virtual `+0x70`** followed by GTF2-owned `0x63b32c` and `0x63b2bc` to obtain **two 16-bit identifiers**; set output flag **1**.
5. `0x118a8c–0x118b2c`: if no visible context was selected, retain the first usable candidate and derive identifiers from it. Diagnostics distinguish this fallback from the visible-context case.
6. `0x118b48–0x118b58`: clean up the temporary context collection.

**Architecture implication:** a “view” can expose **multiple display contexts**, and GTF2 selects an active/visible one or falls back to the first usable context. Therefore mapping a numeric view ID to a single flat screen is insufficient to fully describe center/popup rendering. The two returned 16-bit IDs and output flag should be traced into `handleViewSwitchCenter` and `doSwitch`.

**Scope limitation:** the helper's visible-context predicate is established by the diagnostic and its branch; the semantics of `0x1355f8`, `0x63b32c` and `0x63b2bc` are not yet fully reconstructed. Do not assign names to the two output IDs without checking those callsites.

### Reproduction

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x1189a0 --stop 0x118b78
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x119688 --stop 0x119a50
```

**Updated GTF2-owned call hierarchy:**

```text
ViewManager::handleViewSwitch   [0x11a250; virtual +0x50]
  -> ViewManager::handleViewSwitchCenter [0x118c74; virtual +0x5c]
      -> ViewManager::doSwitch [0x119688; virtual +0x60]
      -> contextIdFromView [0x1189a0] (display-context selection)
```

## Display context IDs traced into transition selection: 16-bit IDs, low-byte classification, code 25

**Original GTF2 ELF disassembly** establishes the complete local use of the two outputs from `contextIdFromView` in `ViewManager::handleViewSwitchCenter`. This is a useful refinement of the previous “two IDs” finding: the caller does **not** directly pass the 16-bit values to the animation launcher. It uses their **low bytes** to classify old/new display contexts and select an internal transition code.

### Exact call and stack layout

At **`0x119010–0x119060`**, the coordinator initializes:

- **`[sp+0xcc]`**: signed 16-bit first output, initialized to **-1**;
- **`[sp+0xca]`**: signed 16-bit second output, initialized to **-1**;
- **`[sp+0xcf]`**: one-byte “visible context found” flag, initialized to **0**.

When a current view exists and either the candidate or current view has view-type value **3** (from GTF2 helper `0x146320`), it calls:

```text
0x119048..0x119060:
    r0 = this
    r1 = this+0x18  (current view)
    r2 = &stack[0xcc]  (first 16-bit ID)
    r3 = &stack[0xca]  (second 16-bit ID)
    stack[0] = &stack[0xcf]  (visibility flag)
    BL 0x1189a0  (contextIdFromView)
```

The same helper is called for the **candidate/new view** at **`0x11909c–0x1190c8`**, with output addresses **`[sp+0xc8]`**, **`[sp+0xc6]`**, and flag **`[sp+0xce]`**.

At **`0x1190cc–0x1190e8`** the coordinator reads **only the low byte** of the first output from each call:

```text
old_category = gtf2_function_0x132050(*(uint8_t *)&old_first_context_id)
new_category = gtf2_function_0x132050(*(uint8_t *)&new_first_context_id)
if old_category == new_category:
    transition_code = 25
else:
    transition_code = (this+0x26 != 0) ? 8 : 2
```

**Important branch constraint:** the comparison/classification is reached only when the relevant view-type tests and non-null candidate conditions pass (`0x119088–0x11909c`). It is **not** a universal transition rule for every screen. The visibility flags and second 16-bit outputs are initialized and filled but are **not read** in this local classification block; other code may consume these values elsewhere.

### Context-byte category function at `0x132050`

This function is a GTF2-local, straight-line ARM classifier with return values in **0..15**. Representative **verified** byte cases:

| Input byte | Return category | Evidence |
| --- | --- | --- |
| `0x00..0x0f` | **14** | `0x132050–0x132054`, default `0x132188` |
| `0x10..0x1f` | **6** | `0x132058–0x132068` |
| `0x20..0x2f` | **4** | `0x13206c–0x13207c` |
| `0x30..0x3d`, `0x3f` | **5** | `0x132080–0x1320a4` |
| `0x3e` | not 5 | explicit exception at `0x132094` |
| `0x4a` / `0x4b` | **12** / **13** | `0x1320a8–0x1320bc` |
| `0x40..0x4f` (other than exceptions) | **15** | `0x1320c0–0x1320d0` |
| `0x50..0x7f` | **7** | `0x1320d4–0x1320e8` |
| `0x80..0x8f` | **1** | `0x1320ec–0x1320f8` |
| `0xae` / `0xaf` | **8** / **9** | `0x13210c–0x132120` |
| `0xb8` | **3** | `0x132124–0x13212c` |
| `0xb0..0xbf` (except `0xb8`) | **0** | `0x132130–0x132140` |
| `0xc0..0xc1` | **10** | `0x132144–0x132154` |
| `0xf0..0xf8` | **2** | `0x132168–0x132178` |
| `0xff` | **11** | `0x13217c–0x132184` |

The exception **`0x3e`** and the precise treatment of **`0x50..0x7f`** follow the order of tests in the machine code; this table is intentionally not a claim about symbolic meanings (e.g. left/right cluster display) of the categories.

### Where the context IDs come from

The first 16-bit ID is derived by calling the selected context's **virtual `+0x70`**, then GTF2 function **`0x63b32c`** (`0x118a50–0x118a70`). The second uses the same virtual getter followed by **`0x63b2bc`** (`0x118a64–0x118a84`). The helper `0x63b32c` reads the context-related object's **`+0xec`** field directly when bit **2** of `+0xfc` is clear, otherwise uses a dependent object at `+0xf0`; `0x63b2bc` similarly reads **`+0xf4`** when bit **4** is clear, otherwise uses `+0xf8`. These are **GTF2-internal data-access routines**; their full object types are not established.

### Consequence for emulation

The **first context identifier's low byte determines a coarse context category**. When both views are of the relevant type and old/new categories match, the transition coordinator selects **code 25**; otherwise it chooses **2** (center mode) or **8** (popup mode). Thus, a faithful QEMU reproduction of view switching may need **both view type and display-context category**, not only numeric view ID. Code 25 is an internal transition/animation selector; its human-readable name remains unverified.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x119010 --stop 0x119110
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x132050 --stop 0x132190
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x63b2bc --stop 0x63b390
```

### Additional verification: `0x146320` is a virtual property forwarding wrapper

Disassembly of GTF2 function **`0x146320–0x146370`** shows it is **not** a hardcoded view-type classifier. After optional diagnostic work, it loads the input object's vptr, dispatches **virtual `+0x74`**, and tail-calls GTF2 helper **`0x63677c`**. Similarly, **`0x146200`** dispatches the same vptr slot `+0x74` and tail-calls **`0x63693c`**. The numerical values compared with **3** in the center coordinator therefore come from **a view property returned through virtual dispatch and a subsequent GTF2 conversion**; their precise symbolic enum names remain unknown.

This narrows the remaining view-class mapping task: recover the concrete **view vtables and their `+0x74` implementations**, then connect these to the property/conversion helpers. It would be incorrect to label value 3 as a particular named dashboard screen at this point.

One edge case in the category table above can be resolved exactly: **byte `0x3e` is category 7**, not category 5. The code explicitly excludes it from the `0x30..0x3f` category-5 branch and includes it in the later category-7 branch (`0x1320d8–0x1320e8`). The table's “not 5” entry should be read as **7**.

Reproduce:

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x146200 --stop 0x146380
```

## GTF2 view-object vtable candidate census and shared notification implementation

A direct, read-only scan of the original GTF2 ELF found **94 candidate pointer-table starts** in `0x7b0000..0x8c0000` with at least **30 consecutive callable-looking entries**, including a callable **`+0x74`** entry. This is a **heuristic census**, not 94 confirmed C++ classes: runs of function pointers can be non-vtable structures, and alignment/pointer-boundary assumptions can introduce false positives. The reproducible scanner is `tools/fpk1/research/gtf2/scan_view_vtables.py`.

Several strong, structurally similar candidates demonstrate that the previous view-property call can dispatch to **different GTF2-owned methods** depending on the object's vptr:

| Candidate table VA | `+0x00` | `+0x4c` | `+0x74` | `+0x78` |
| --- | --- | --- | --- | --- |
| `0x7c5518` | `0x135594` | `0x145198` | `0x1355f0` | `0x143a54` |
| `0x892df0` | `0x6aea64` | `0x145198` | `0x6aeae0` | `0x143a54` |
| `0x893098` | `0x6af270` | `0x145198` | `0x6af2ec` | `0x143a54` |
| `0x893450` | `0x6afa60` | `0x145198` | `0x6afabc` | `0x143a54` |
| `0x895458` | `0x6baa44` | `0x145198` | `0x6baaa0` | `0x143a54` |

The shared **`+0x4c -> 0x145198`** is a substantial GTF2 routine, not the simple `BaseViewManager` getter at `0x1173d4`. Its entry at `0x145198` loads the receiver's vptr and invokes its **virtual `+0x70`** at `0x1451b4–0x1451b8`, then continues into GTF2-owned `0x6218cc`. This supplies concrete evidence that the **view receiver's `+0x4c` callback** used by the DP flush path may be a shared adapter that delegates through another virtual slot. The precise relationship of these five candidate tables to the receiver objects passed at `0x122338` still needs constructor tracing.

**Practical next step:** instead of treating `+0x74` as a single method, cross-reference each candidate table's vptr literal against constructor stores; inspect the per-class `+0x74` methods (`0x6aeae0`, `0x6af2ec`, `0x6afabc`, etc.), then map the constructed objects into the provider lookup `0x6a9e9c`. Do not equate these candidate tables with named screens until those links are proven.

### Reproduce the census

```sh
python3 tools/fpk1/research/gtf2/scan_view_vtables.py /path/to/gtf2 \
  --start 0x7b0000 --stop 0x8c0000 --code-stop 0x7b0000 --min-methods 30
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 \
  --start 0x145198 --stop 0x1451c0
```

## Five candidate view tables confirmed by constructor vptr writes; +0x74 is an object link

The preceding 94-table scan was heuristic. A follow-up checked **literal references and ARM constructor instructions** for five representative candidates. All five have actual GTF2-owned routines that **write the candidate vtable address to the beginning of an object**. This upgrades these five from “pointer-array candidates” to **confirmed object vtables**, without yet proving their screen names.

| Vtable | Exact pointer literals in GTF2 code | Example confirmed `STR` of vptr |
| --- | --- | --- |
| `0x7c5518` | `0x135fd0`, `0x135ff0`, `0x136028` | `0x135fb8: str r3,[r0]`; `0x136014: str r2,[r4]` |
| `0x892df0` | `0x6aec40`, `0x6aec60`, `0x6aec80` | `0x6aec28: str r3,[r0]`; `0x6aec78: str r3,[r4]` |
| `0x893098` | `0x6af3d0`, `0x6af3f0`, `0x6af410` | `0x6af3b8: str r3,[r0]`; `0x6af408: str r3,[r4]` |
| `0x893450` | `0x6b08bc`, `0x6b08fc`, `0x6b099c` | `0x6b0888: str r3,[r0],#392`; `0x6b093c: str r3,[r4]` |
| `0x895458` | `0x6bad84`, `0x6badc8`, `0x6badf8` | `0x6bad98: str r3,[r0],#320`; `0x6badec: str r2,[r4]` |

**Important offset nuance:** the post-index stores in the `0x893450` and `0x895458` constructors write the vptr at the **original** `r0` address, then advance `r0`. They do **not** place the vptr at `this+392` or `this+320`.

### Exact slot implementations for all five

| Table | `+0x4c` | `+0x70` | `+0x74` |
| --- | --- | --- | --- |
| `0x7c5518` | `0x145198` | `0x1355e8` | `0x1355f0` |
| `0x892df0` | `0x145198` | `0x6aead8` | `0x6aeae0` |
| `0x893098` | `0x145198` | `0x6af2e4` | `0x6af2ec` |
| `0x893450` | `0x145198` | `0x6afab4` | `0x6afabc` |
| `0x895458` | `0x145198` | `0x6baa98` | `0x6baaa0` |

**All ten `+0x70` and `+0x74` functions are identical two-instruction getters** in these five concrete vtables:

```arm
    ldr r0, [r0, #4]
    bx  lr
```

This is a major refinement of the previous discussion of “view properties.” For these classes, the virtual `+0x74` **does not itself classify the view**. It returns an object pointer from **`this+0x04`**, which GTF2 then passes to `0x63677c` (via `0x146320`) or `0x63693c` (via `0x146200`). The classification is downstream of this pointer. Likewise, `+0x70` returns the same `this+0x04` pointer, which is passed to GTF2 helper `0x6218cc` in the common **`+0x4c -> 0x145198`** notification adapter.

**Architecture consequence:** the five confirmed view-like classes share a common **object-link/adapter pattern**:

```text
view object (vptr = one of five confirmed tables)
  +0x04 -> linked inner object
  virtual +0x70 / +0x74 -> return linked inner object
  virtual +0x4c -> 0x145198
       -> linked inner object -> 0x6218cc -> further notification dispatch
  0x146320(view)
       -> linked inner object -> 0x63677c -> numeric property
  0x146200(view)
       -> linked inner object -> 0x63693c -> another property
```

This **does not prove** that all five are top-level screens, that they are registered in the `0x6a9e9c` view provider, or that every concrete GTF2 view uses this pattern. Constructor-to-provider registration is the next necessary link.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/trace_view_constructors.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6aec1c --stop 0x6aec84
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6b087c --stop 0x6b09a4
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x145198 --stop 0x145220
```

## Breakthrough: view-provider dispatch connected to a 179-key lazy object factory

**Verified by direct ARM disassembly and ELF data**, this section closes the previously missing link between `0x6a9e9c` (view lookup), global provider initialization, and a concrete keyed object factory.

### Provider registration chain

1. The GTF2-owned initialization function **`0x222070`** calls **`0x25a8f4`** at **`0x22207c`**. It passes the return pointer directly into **`0x6a9ef4`** at **`0x222080`**.
2. **`0x6a9ef4`** stores that pointer into the global provider slot **`0xdb1900`** (`STR r0,[r3]` at `0x6a9ef8`). This is the **only direct BL callsite** to `0x6a9ef4` in the scanned executable PT_LOAD.
3. **`0x25a8f4`** implements one-time initialization of a static provider object at **`0xd502b8`**, using a guard at **`0xabed10`** and installing the vptr **`0x82bdd8`** (`0x25a918–0x25a928`); it returns `0xd502b8` at `0x25a92c`.
4. The provider vtable at **`0x82bdd8`** begins with the following verified entries:

   | Slot | Function |
   | --- | --- |
   | `+0x00` | **`0x25a940`** (179-key object lookup/factory) |
   | `+0x04` | `0x25df30` |
   | `+0x08` | `0x239a7c` |

5. The GTF2 view lookup wrapper **`0x6a9e9c`** loads global `[0xdb1900]` and calls its **virtual `+0x00`** with the requested numeric ID. Therefore, **after the provider registration above**, the lookup dispatches to **`0x25a940`**. This is the missing verified connection between the ViewManager's view lookup and the keyed factory.

### Exact key handling in `0x25a940`

The factory receives the requested ID in **`r1`**, with the provider pointer in `r0`:

- `0x25a940–0x25a950`: **ID 0** clears the temporary result slot and returns null.
- `0x25a954–0x25a964`: subtract 1, bounds-check **0..178** and dispatch through a **179-entry ARM PC-relative jump table** at **`0x25a968`**. Out-of-range values go to default **`0x25bd7c`**.
- **92** IDs map to a distinct case handler; **87** IDs share the null-result handler **`0x25bd7c`**. Each supported handler checks a per-ID singleton holder's `+0x04` field; if null, calls a GTF2-owned initializer, then loads the resulting object pointer.
- `0x25bd84–0x25bd8c`: returns the pointer from the common temporary result slot at **`0xd502b4`**. The slot is reused for each call; the caller receives the object pointer in `r0`.

**The supported IDs (92):**

```text
1–8, 18–26, 60–72, 96–101, 111–122, 132–149,
152, 154–159, 160–174, 176–179
```

The ranges above are a compact representation of the actual case table; verify any individual key using the script. The **87 other IDs** in 1..179 are **not mapped by this provider in this firmware build**. This does **not** mean those IDs cannot occur in events, other namespaces, or alternate firmware builds.

**Concrete initial keys:**

| View ID | Case | Singleton holder | Lazy initializer |
| --- | --- | --- | --- |
| 1 | `0x25b1b4` | `0xc79a40` | `0x341e30` |
| 2 | `0x25b1e0` | `0xb402e0` | `0x383098` |
| 3 | `0x25b238` | `0xc4f360` | `0x344a40` |
| 4 | `0x25b188` | `0xaff770` | `0x373b88` |
| 5 | `0x25b290` | `0xd50888` | `0x342530` |
| 6 | `0x25b264` | `0xd16ec0` | `0x343398` |
| 7 | `0x25b15c` | `0xb5ea24` | `0x342444` |
| 8 | `0x25b20c` | `0xbfb2b0` | `0x3824f0` |

**This is the first direct, code-proven numeric ViewManager lookup → ID → GTF2 object initializer map.** Symbolic names and concrete visual layouts of those 92 views remain to be determined, but the prior uncertainty about whether the factory was actually used by the ViewManager is now resolved.

### Important correction to prior hypotheses

The previously examined base table **`0x7bdad8`** has virtual slot `+0x00 -> 0x113e0c`, a constructor-like vptr initializer, and **is not** the active provider vtable after `0x222070`. The actual registered provider's vtable is **`0x82bdd8`**. The distinction is proven by the exact pointer stored in `0xdb1900` and the vptr written to `0xd502b8`.

### Reproduction

```sh
python3 tools/fpk1/research/gtf2/inspect_lazy_object_factory.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x222070 --stop 0x222090
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x25a8f4 --stop 0x25a940
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x25a940 --stop 0x25a968
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a9e9c --stop 0x6a9f04
```

**Next GTF2-only target:** follow representative initializer functions `0x341e30`, `0x383098`, `0x344a40` to identify actual object vptrs and diagnostic class/screen names; then systematically connect the 92 mapped IDs to their concrete view classes and DP subscription slots.

## First concrete screen names recovered from the registered view factory

Following the provider-to-factory proof above, the **per-ID initializer functions contain literal references to `SV_*` view names and `CHMI*ViewData::construct` diagnostic names**. A reproducible scanner, `map_view_names.py`, follows the **92 supported factory branches** and reads only string literals directly referenced by their GTF2-owned initializer prologues.

With a deliberately conservative **128-byte initializer scan**, **62 of the 92** supported view IDs already yield an exact embedded **`SV_*`** screen name. The remaining **30 are unresolved by this shallow scan**, not absent. These are **actual names embedded in this firmware**, not speculative UI labels.

### Concrete view-ID map (representative confirmed names)

| ID | Exact GTF2 view name | Initializer |
| --- | --- | --- |
| **1** | `SV_AudioFPK_HinweisTexte` | `0x341e30` |
| **2** | `SV_AudioFPK_MediaBrowser` | `0x383098` |
| **3** | `SV_AudioFPK_ReceptionList` | `0x344a40` |
| **4** | `SV_AudioFPK_FavoritesList` | `0x373b88` |
| **5** | `SV_AudioFPK_TuneScanMode` | `0x342530` |
| **6** | `SV_AudioFPK_StationListUpdate` | `0x343398` |
| **7** | `SV_AudioFPK_Empty` | `0x342444` |
| **8** | `SV_AudioFPK_NA` | `0x3824f0` |
| **18** | `SV_BordComputer` | `0x3b0db8` |
| **19** | `SV_Car_Sportfunktionen_Laptimer` | `0x3fb848` |
| **20** | `SV_Car_Sportfunktionen_Sportanzeigen` | `0x3f3748` |
| **21** | `SV_Car_Sportfunktionen_Statistik` | `0x3e5588` |
| **22** | `SV_Car_EnergyFlow` | `0x43d470` |
| **23** | `SV_Car_ReducedView` | `0x4382c0` |
| **24** | `SV_Car_Submenu_HybridDisplayMode` | `0x40fdd8` |
| **25** | `SV_Car_Submenu_AdditionalDisplays` | `0x413320` |
| **26** | `SV_Car_Submenu_AdditionalDisplays_Sport` | `0x4192b0` |
| **60** | `SV_Car_Layout_WaitLayoutSwitching` | `0x40e478` |
| **61** | `SV_Car_Layout_LayoutChoice` | `0x4384fc` |
| **62** | `SV_Car_Layout_Disclaimer` | `0x43a980` |
| **63** | `SV_Car_Layout_LayoutChoice_InitialBigStage` | `0x438a1c` |
| **64** | `SV_Car_Layout_VelocityThreshold` | `0x438f30` |
| **65** | `SV_NightVision` | `0x40d1c8` |
| **66** | `SV_NightVision_Init` | `0x40d978` |
| **67** | `SV_Welcome_EnergyFlow` | `0x40b978` |
| **71** | `SV_Test_Font` | `0x459220` |
| **72** | `SV_TransportMode` | `0x44bb48` |
| **96** | `SV_Empty` | `0x44b958` |
| **97** | `SV_Safe_CP` | `0x44e2f0` |
| **98** | `SV_LogoAnimGoodbye` | `0x460c8c` |
| **99** | `SV_LogoAnimWelcome` | `0x4607a0` |
| **100** | `SV_Empty_Startup` | `0x44ba44` |
| **111** | `SV_Nav_Submenu_Autozoom` | `0x476cc8` |
| **112** | `SV_Nav_Submenu_MapColor` | `0x4737d0` |
| **113** | `SV_Nav_Submenu_MapDisplay` | `0x4702e0` |
| **114** | `SV_Nav_Submenu_MapType` | `0x46ade8` |
| **115** | `SV_Nav_Submenu_Voice` | `0x466ea0` |
| **116** | `SV_LVDS_FPK_NavMap` | `0x4a2a48` |
| **117** | `SV_NavFPK_Favourites` | `0x4961d0` |
| **118** | `SV_NavFPK_LastDestinations` | `0x487040` |
| **119** | `SV_NavFPK_Compass` | `0x4a2698` |
| **120** | `SV_NavFPK_Compass_MobileDevice` | `0x466da4` |
| **121** | `SV_NavFPK_HinweisTexte` | `0x4a20b8` |
| **122** | `SV_NavFPK_NA` | `0x47a1b8` |
| **132** | `SV_Phone_NA` | `0x4cc910` |
| **133** | `SV_Phone_AutoRedialing` | `0x4cf260` |
| **134** | `SV_Phone_EmergencyCall_Confirm` | `0x50abb8` |
| **135** | `SV_Phone_HinweisTexte` | `0x4d63f8` |
| **136** | `SV_Phone_NoListsAvailable` | `0x4cc334` |
| **137** | `SV_Phone_ActiveCall_MultipleCalls` | `0x5276d8` |
| **138** | `SV_Phone_ActiveCall_OneCall` | `0x538bb0` |
| **139** | `SV_Phone_Adressbook_DetailedNumbers` | `0x5039e8` |
| **140** | `SV_Phone_Adressbook_Overview` | `0x50d0e0` |
| **141** | `SV_Phone_CombinedNumbers` | `0x4e3a08` |
| **142** | `SV_Phone_Mailbox_NotAvailable` | `0x4cd4b8` |
| **143** | `SV_Phone_Favorites` | `0x4d69c8` |
| **144** | `SV_Phone_AudiService` | `0x4d0f68` |
| **145** | `SV_Phone_AudiService_InfoCall` | `0x4d44e8` |
| **146** | `SV_Phone_AudiService_ServiceCall` | `0x4d25e0` |
| **152** | `SV_WarnRoller` | `0x54b720` |
| **172** | `SV_Test_ImageDecorator` | `0x54aa28` |
| **179** | `SV_DEBUG_List` | `0x5617a0` |

**Important distinction:** this table names *view IDs in the active provider* and their lazy initializer routines, not the **180 DP subscription slots**. The numeric ranges overlap, but a direct proof that every view ID equals its DP subscription slot has not been established. The special transition sentinel **181** is outside the provider's 1..179 factory range.

### Verified chain, end to end

```text
GTF2 startup 0x222070
  -> 0x25a8f4: construct singleton provider, vptr 0x82bdd8
  -> 0x6a9ef4: register provider in global 0xdb1900
ViewManager view lookup
  -> 0x6a9e9c: provider virtual +0x00
  -> 0x25a940: 179-entry ID jump table
  -> per-ID lazy singleton initializer
  -> named CHMI*ViewData::construct / SV_* screen
```

This is the first **end-to-end mapping from GTF2's active ViewManager provider to named application screens**. Next: resolve the 30 shallow-scan misses, then follow specific view constructors to their DP subscriptions and UI event handlers.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/map_view_names.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/inspect_lazy_object_factory.py /path/to/gtf2
```

## Remaining 30 factory IDs resolved to CHMI ViewData constructor diagnostics

The previous conservative `SV_*` string scanner resolved **62/92** supported view IDs. A second pass over the **original GTF2 ELF** identified direct pointers to `CHMI*ViewData::construct` diagnostic strings in the corresponding **30** lazy initializer functions. This establishes a firmware-embedded **class/construction diagnostic** for every previously unnamed ID, while preserving the distinction between an exact `SV_*` visual screen name and a C++ `ViewData` constructor name.

| Factory ID | Direct constructor diagnostic | Initializer | Literal pointer site |
| --- | --- | --- | --- |
| 68 | `CHMIPvOpensourcelicensesViewData::construct` | `0x43edc8` | `0x43f760` |
| 69 | `CHMIPvOpensourcelicensesLoadingViewData::construct` | `0x40f528` | `0x40fd18` |
| 70 | `CHMIMvSlideshowscreenViewData::construct` | `0x461150` | `0x4613d4` |
| 101 | `CHMIPvVersionsViewData::construct` | `0x44ed60` | `0x44f4d8` |
| 147 | `CHMIPvIncomingcallViewData::construct` | `0x543288` | `0x543a48` |
| 148 | `CHMIPvPpPhoneCallactionresultViewData::construct` | `0x542120` | `0x5428d0` |
| 149 | `CHMIPvPhoneNotificationViewData::construct` | `0x5429b8` | `0x5431c8` |
| 154 | `CHMIPvPartialpopupbapViewData::construct` | `0x557ba8` | `0x558350` |
| 155 | `CHMIPvWarnpopupCaroutlineViewData::construct` | `0x5578a0` | `0x557b54` |
| 156 | `CHMIPvWarnpopupDsssViewData::construct` | `0x5569b8` | `0x556dc8` |
| 157 | `CHMIPvWarnpopupEspsupersportViewData::construct` | `0x555da8` | `0x5565dc` |
| 158 | `CHMIPvWarnpopupFuelViewData::construct` | `0x554a38` | `0x555168` |
| 159 | `CHMIPvWarnpopupLogewaViewData::construct` | `0x5544a8` | `0x5549bc` |
| 160 | `CHMIPvWarnpopupOilViewData::construct` | `0x5536a0` | `0x554128` |
| 161 | `CHMIPvWarnpopupPhevViewData::construct` | `0x557138` | `0x55741c` |
| 162 | `CHMIPvWarnpopupPlaViewData::construct` | `0x552c78` | `0x553670` |
| 163 | `CHMIPvWarnpopupPpBcmeViewData::construct` | `0x551ea8` | `0x55275c` |
| 164 | `CHMIPvWarnpopupPpEtronreadyViewData::construct` | `0x556e40` | `0x5570e8` |
| 165 | `CHMIPvWarnpopupPpStdViewData::construct` | `0x550c08` | `0x5513ac` |
| 166 | `CHMIPvWarnpopupPpStdiconViewData::construct` | `0x551490` | `0x551e80` |
| 167 | `CHMIPvWarnpopupPerformancestellringViewData::construct` | `0x557470` | `0x557844` |
| 168 | `CHMIPvWarnpopupStdViewData::construct` | `0x54ef00` | `0x54f708` |
| 169 | `CHMIPvWarnpopupStdiconViewData::construct` | `0x54f7e8` | `0x550010` |
| 170 | `CHMIPvWarnpopupStdiconbigViewData::construct` | `0x550260` | `0x550bc4` |
| 171 | `CHMIPvWarnpopupVerdeckViewData::construct` | `0x54eb20` | `0x54ee9c` |
| 173 | `CHMIPvAccPopupViewData::construct` | `0x54a95c` | `0x54aa18` |
| 174 | `CHMIMvClusterblackscreenViewData::construct` | `0x5d16a8` | `0x5d18ac` |
| 176 | `CHMIMvClusterfullViewData::construct` | `0x59f678` | `0x5a0048` |
| 177 | `CHMIMvClusterearlytubesViewData::construct` | `0x5cc5c8` | `0x5cd5d8` |
| 178 | `CHMIMvEarlywelcomeViewData::construct` | `0x59daa0` | `0x59eaa8` |

**Important limitation:** the scanner reads the **first `CHMI*ViewData::construct` pointer within 0x3000 bytes** of the lazy initializer, and some constructors are longer than others. Each table entry is backed by an exact literal site, but the literal-to-code reference and function boundary should still be verified when making a stronger claim about object creation. In particular, these are not necessarily the exact `SV_*` resource identifiers, and the strings alone do not prove the object's final visual appearance.

### Key architectural result for FPK1 startup

IDs **174, 176, 177, 178** are the firmware's **cluster startup/full/early** ViewData classes:

```text
174 -> CHMIMvClusterblackscreenViewData
176 -> CHMIMvClusterfullViewData
177 -> CHMIMvClusterearlytubesViewData
178 -> CHMIMvEarlywelcomeViewData
```

This is a concrete link between the **named view factory** and the earlier GTF2 **EarlyTubes / ClusterFull / startup resource** analysis. The exact transition sequence among these IDs is **not** established by their names alone; next inspect callers that request these IDs and their event paths.

### Reproduction

```sh
python3 tools/fpk1/research/gtf2/map_view_construct_diagnostics.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/map_view_names.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x543288 --stop 0x5433b0
```

**Coverage statement:** 62 supported IDs have `SV_*` names via the shallow initializer scan, and the other 30 have `CHMI*ViewData::construct` diagnostics. Hence **92/92 factory-supported IDs have a firmware-derived identifier**, but **not** 92 confirmed `SV_*` names, 92 proven visual screen layouts, or 92 mapped DP event handlers.

## Complete 179-name view registry: provider virtual +0x04 is a canonical ID-to-name resolver

A direct disassembly of the registered provider's **second virtual method**, **`+0x04 -> 0x25df30`**, reveals a second **179-entry jump table** at **`0x25df48`**, parallel to the previously decoded object factory `+0x00 -> 0x25a940`.

This is a **major correction and improvement** over the previous heuristic `SV_*` and `CHMI*ViewData::construct` scans. The firmware itself implements a direct **ID -> canonical view name** function, covering **all 179 IDs**, including the 87 IDs that do not have a local lazy object initializer.

### Exact implementation

- `0x25df30–0x25df44`: subtract 1 from input `r1`, compare against 178, dispatch through **179-entry** table `0x25df48`.
- Each in-range case is two instructions, a PC-relative **`LDR r0,[pc,#offset]`** and **`POP {r4,pc}`**. The loaded pointer addresses a NUL-terminated canonical view-name string in the GTF2 ELF.
- For example, **ID 1** jumps to `0x25e21c`, whose literal at `0x25e7c8` points to `0x816c2c` = **`SV_AudioFPK_HinweisTexte`**. **ID 2** jumps to `0x25e214`, literal `0x25e7c4` points to `0x816c45` = **`SV_AudioFPK_MediaBrowser`**.
- **`0x6a9ec8`** calls provider virtual `+0x04`; it has **28 direct GTF2 BL callsites** in the executable. This is the view-name lookup already used in `ViewManager` diagnostics, including `0x118b9c`, `0x118ca8`, `0x1196b8`, `0x11a284`, and `0x11a69c`.
- The registered provider vtable `0x82bdd8` therefore exposes **two separate registries** over the same numeric ID namespace: **`+0x00`** returns a lazily created view object (or null), while **`+0x04`** returns its **canonical diagnostic name**.

**Full verified coverage:** **179/179 names**, **92/179 object-factory-supported**, **87/179 name-only**. “Name-only” means this provider's local object factory returns null for the ID; it does **not** prove the feature is absent elsewhere in the system or cannot be displayed by a different renderer.

### Previously unresolved 30 IDs now have exact canonical names

| ID | Canonical name from `+0x04` | Earlier constructor diagnostic |
| --- | --- | --- |
| 68 | `PV_OpenSourceLicenses` | `CHMIPvOpensourcelicensesViewData::construct` |
| 69 | `PV_OpenSourceLicenses_Loading` | `CHMIPvOpensourcelicensesLoadingViewData::construct` |
| 70 | `MV_SlideShowScreen` | `CHMIMvSlideshowscreenViewData::construct` |
| 101 | `PV_Versions` | `CHMIPvVersionsViewData::construct` |
| 147 | `PV_IncomingCall` | `CHMIPvIncomingcallViewData::construct` |
| 154 | `PV_PartialPopupBAP` | `CHMIPvPartialpopupbapViewData::construct` |
| 173 | `PV_ACC_Popup` | `CHMIPvAccPopupViewData::construct` |
| 174 | `MV_ClusterBlackScreen` | `CHMIMvClusterblackscreenViewData::construct` |
| 176 | `MV_ClusterFull` | `CHMIMvClusterfullViewData::construct` |
| 177 | `MV_ClusterEarlyTubes` | `CHMIMvClusterearlytubesViewData::construct` |
| 178 | `MV_EarlyWelcome` | `CHMIMvEarlywelcomeViewData::construct` |

All 30 have an exact canonical name in the registry; the table shows representative high-value IDs. For the complete 179-row mapping, run the committed script below.

### Crucial distinction: named IDs without local view objects

| ID | Canonical registry name | Factory `+0x00` |
| --- | --- | --- |
| 9 | `SV_LVDS_Audio` | null |
| 27 | `SV_LVDS_Car_Bordbuch` | null |
| 59 | `SV_LVDS_Car_View360_NA_Off` | null |
| 73 | `SV_MainWizard` | null |
| 74 | `SV_LVDS_AudiConnect` | null |
| 123 | `SV_LVDS_B_Call` | null |
| 150 | `PV_PP_SmartphoneNotConnected` | null |
| 151 | `SV_WarnRoller_Clamp15Off` | null |
| 153 | `PV_LVDS_MMI_Popup` | null |
| **175** | **`MV_ClusterFull_BY`** | **null** |

The **ID 175** result is particularly useful for startup reconstruction: the registry **knows** `MV_ClusterFull_BY`, but the **active object factory has no implementation** for it in this firmware build. By contrast **174, 176, 177, 178** all have concrete lazy initializers. Therefore the startup view inventory must distinguish **named-but-uninstantiable** from **locally instantiated** views, not infer availability from names alone.

### Reproduce the complete canonical map

```sh
python3 tools/fpk1/research/gtf2/map_provider_names.py /path/to/gtf2 > build_fpk1/research-artifacts/gtf2-provider-names.csv
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x25df30 --stop 0x25df70
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a9ec8 --stop 0x6a9ef4
```

This is an **exact decoder of a firmware-implemented lookup table**, rather than a heuristic string scan. No proprietary ELF bytes are committed. The next GTF2-owned task is to trace **who requests startup IDs 174/176/177/178** and whether the object provider is invoked before or after the EarlyTubes/ClusterFull KZB gates.

## KZB startup requests are per-view resource preparation, not view activation

A direct reconstruction of the **GTF2-owned** helper **`0x1217c8`** resolves the earlier ambiguity around ID constants in `handleLoadingKZBs`.

```text
prepareViewResources(this, view_id, resource_batch):
  provider = 0x25a8f4()                # registered provider singleton
  view = provider->virtual_0x00(view_id) # 0x25a940 lazy factory
  if view != NULL:
      view->virtual_0x88(resource_batch)
  else:
      log view_id at debug level (0x121804..0x121824)
```

The direct call sequence is **`0x1217d4 -> 0x25a8f4`**, virtual `+0x00` at **`0x1217dc–0x1217e4`**, and **view virtual `+0x88`** at **`0x1217f0–0x1217fc`**. This is an **application-owned view resource hook**, not a `ViewManager::handleViewSwitch` call. It can create the ViewData singleton as a side effect of lazy lookup; it does not prove the view was shown.

### Exact startup batches in `handleLoadingKZBs`

| Stage / gate | Direct calls | Meaning |
| --- | --- | --- |
| EarlyTubes, `this+0xdf5==0` | `0x122f70`: **174** (`MV_ClusterBlackScreen`); `0x122f80`: **177** (`MV_ClusterEarlyTubes`) | Prepare two views with the **same batch pointer** in `r2`, then enqueue a resource operation at `0x122fdc`; set `+0xdf5=1` at `0x122fec` |
| ClusterFull, `+0xdf7==0` and `+0xdf6!=0` | `0x123074`: **178** (`MV_EarlyWelcome`); `0x123084`: **99** (`SV_LogoAnimWelcome`); additional popup and warning IDs at `0x123120..0x123248` | Prepare the larger cluster/welcome/warning batch, enqueue at `0x123100` and `0x123258`; set `+0xdf7=1` at `0x12332c` |
| ClusterFull supplemental ID list | `0x123260–0x123304` | Obtain mode-specific ID array and call the same `0x1217c8` hook for IDs **not excluded by the explicit filter** |
| 3D car, `+0xdf9==0` and `+0xdf8!=0` | `0x12333c–0x123484` | Wait on signed counter, then enqueue a distinct 3D-related operation and set `+0xdf9=1` |

**Crucial correction:** the presence of `174`, `177`, `178`, `99` in the batch is evidence of **resource-preparation ordering**, not of a rendered screen sequence. The current evidence **does not establish** whether `MV_ClusterBlackScreen` becomes visible before `MV_ClusterEarlyTubes`, or whether `MV_EarlyWelcome` is shown at all.

### Mode-indexed supplemental view lists: 16 entries

The call at **`0x123260`** invokes GTF2 function **`0x69e144(6)`**. Its result is mapped at `0x123268–0x12327c` to **mode 2 if result==0**, **mode 14 if result==256**, or **mode 0 otherwise**. The GTF2 provider method **`0x239a80`** then resolves the selected mode via a **16-pointer table at `0x8169b8`**, with each non-null pointer referencing a zero-terminated array of numeric view IDs. The exact meaning of `0x69e144(6)` and the two modes is **not yet established**; avoid naming them “skin 2/14” without further proof.

A byte-for-byte cross-check of all arrays against the **92-ID object factory** gives:

| Mode(s) | Array length | Supported IDs | Name-only IDs | Missing supported IDs |
| --- | ---: | ---: | ---: | ---: |
| **2, 9, 13, 14, 15, 16** | **92** | **92** | **0** | **0** |
| **1, 4, 5, 10, 12** | **137** | **51** | **86** | **41** |
| **3** | **24** | **23** | **1** (ID **175**, `MV_ClusterFull_BY`) | **69** |
| **6, 7, 8, 11** | null pointer | 0 | 0 | 92 |

The six 92-entry arrays are **exactly the same set** as the active lazy factory's 92 supported IDs, without duplicates, though some arrays have different order. The 137-entry arrays reference **86 IDs for which this firmware's factory returns null**, and the 24-entry mode-3 array contains the named but uninstantiable ID **175**. The `0x1217c8` null check makes such unsupported IDs safe to skip when invoked through this hook.

**One important branch constraint:** the supplemental loop excludes **ID 0**, **99**, **147**, **154..171**, **174**, **177** and **178** before invoking the helper (`0x1232a4–0x1232f8`). Thus a mode array is **not** a literal list of all resource-hook invocations: several views are handled explicitly earlier, and unsupported IDs can be ignored by the helper. In particular, **ID 176 (`MV_ClusterFull`) is *not* in the exclusion set** and can reach the resource hook through the mode list.

### Practical implications for QEMU

- **Do not simulate a view switch when the KZB handler calls `0x1217c8`.** Model it as per-view resource preparation.
- Preserve the gate order **EarlyTubes requested → EarlyTubes handled → ClusterFull requested → ClusterFull handled → 3D request**. The requested/handled flags remain distinct from actual GPU completion.
- A mode-dependent resource walk can include null-returning IDs; **skip them rather than treating them as fatal**, consistent with `0x1217c8`.
- To reconstruct **visible** startup order, trace the actual **`ViewManager::handleViewSwitch` / `doSwitch`** entry points and event payloads independently of these resource requests.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/inspect_kzb_view_groups.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x1217c8 --stop 0x121830
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x122f28 --stop 0x123110
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x123260 --stop 0x123334
```

## Actual screen switching: virtual-dispatch boundaries and a separate state-driven lookup

A new direct-call census of the **original executable PT_LOAD** clarifies why the KZB resource sequence cannot be treated as the visible startup sequence.

| GTF2 method | Address | Direct ARM BL callsites |
| --- | --- | --- |
| `BaseViewManager::handleViewSwitch` | `0x6a91a8` | **1**: `0x11a80c` (derived fallback) |
| `ViewManager::handleViewSwitch` | `0x11a250` | **0** |
| `ViewManager::handleViewSwitchCenter` | `0x118c74` | **0** |
| `ViewManager::doSwitch` | `0x119688` | **0** |
| Provider view lookup `0x6a9e9c` | `0x6a9e9c` | **7** |
| KZB resource preparation `0x1217c8` | `0x1217c8` | **24** |

These counts are for **direct ARM BL calls** in this binary, **not total runtime invocations**. The three derived ViewManager methods are **reachable through virtual dispatch** in the previously verified vtable `0x7bfaf0`: `+0x50`, `+0x5c`, `+0x60`. A zero direct-call count therefore **does not** imply dead code. Conversely, the **24 direct KZB resource-hook calls** cannot be mistaken for 24 visible screen switches.

### Additional state-driven view lookup at `0x6adb08`

The GTF2-owned function **`0x6adb08–0x6adc0c`** independently retrieves a numeric ID from an inner state object at **`this+0x13c`** through its **virtual `+0x08`**, then:

1. Compares the resulting ID with the cached **`this+0x140`** (`0x6adb4c–0x6adb54`).
2. If changed, caches the new ID at **`0x6adb88`**.
3. Calls the registered view provider **`0x6a9e9c`** at **`0x6adb8c`**.
4. If a non-null view is returned, invokes that **view's virtual `+0x00`** with a literal argument from **`0x6adc10`** (`0x6adb9c–0x6adba8`).
5. Stores the result in **`this+0x138`** (`0x6adbac–0x6adbb0`).

The precise semantics of the view's `+0x00` method and the owner of `this+0x13c` are **not yet proven**. This is evidence of a **second state-driven consumer of the ID registry**, not evidence of an actual `ViewManager::doSwitch` transition. In particular, **do not conflate this function's `this+0x140` cache with the ViewManager's `this+0x1c` current view ID**; they belong to different object layouts.

### What is still needed for the visible startup sequence

The missing evidence is **the source and timing of the view-switch request records** consumed by virtual `+0x50`, and the values selected by the GTF2 state machine. The proven KZB order is **resource readiness**, not a screen timeline. Any startup sequence such as “black screen → early tubes → full cluster” is still a **hypothesis**, even though the corresponding view classes and resource-preparation hooks have now been identified.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/trace_view_switch_calls.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6adb08 --stop 0x6adc20
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11a7e0 --stop 0x11a824
```
