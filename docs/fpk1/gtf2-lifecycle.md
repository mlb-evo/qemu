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
