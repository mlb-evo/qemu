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

## View-switch request entry identified: BaseViewManager event callback, not KZB

Direct disassembly now identifies **where the virtual `handleViewSwitch` is invoked**. The earlier direct-BL census missed it because it is a vtable call.

### Vtable ownership and event entry

The **base manager** vtable `0x891958` has:

| Offset | Target | Observed role |
| --- | --- | --- |
| `+0x2c` | **`0x6a96d0`** | event-processing callback |
| `+0x38` | **`0x6a94f4`** | `BaseViewManager::viewSwitch` (diagnostic string `0x891c48`) |
| `+0x50` | **`0x6a91a8`** | `BaseViewManager::handleViewSwitch` |

The **derived manager** vtable `0x7bfaf0` retains **`+0x38 -> 0x11a880`**, **`+0x2c -> 0x11a8bc`**, and overrides **`+0x50 -> 0x11a250`**. Thus the derived event/view-switch methods need separate inspection, but the base code reveals the calling contract.

At **`0x6a96d0`**, the event callback reads **`[r1]`** (event kind) and explicitly recognizes **2**, **8**, and **9** (`0x6a9704–0x6a9728`). It invokes manager virtual **`+0x10`** first (`0x6a9730–0x6a973c`), then calls **virtual `+0x50`** at **`0x6a9798–0x6a97ac`** with `r0=this`, `r1=r2_original`, `r2=&local_result`. This is a **real event → view-switch handler boundary**.

The same event callback has a **second virtual `+0x50` invocation** at **`0x6a9900–0x6a9914`**, after processing current-view notification. In between:

- If current view exists, it excludes **kind 9 / ID 284** from a particular notification path (`0x6a97d8–0x6a97fc`). This matches the previously identified **frame event 284**, but **does not imply** that the entire event callback is skipped.
- For other eligible events, it dispatches to the current view's **virtual `+0x4c`** at **`0x6a9808–0x6a9824`**, passing event, auxiliary argument and local flags. This is the same view callback slot implicated in the 180-slot DP flush mechanism.
- The return code is used to decide whether to process queued events through GTF2 routines **`0x69c574`** and **`0x69d4c8`** (`0x6a984c–0x6a98d4`), before the second switch-handler invocation.

**Implication:** the manager can evaluate a switch **both before and after delivering an event to the active view**, with pending-event/queue handling in between. A simplistic “one event = one switch” emulator would miss this two-pass behavior.

### Separate explicit viewSwitch entry `0x6a94f4`

The base vtable's **`+0x38`** function logs `BaseViewManager::viewSwitch` and invokes virtual **`+0x50`** at **`0x6a9534–0x6a9548`**. If a current view exists, it then performs staged view virtual callbacks **`+0x34`**, **`+0x38`**, and conditionally **`+0x3c`** at `0x6a95b0–0x6a9664`, separated by GTF2-local state updates through `0x6a8cb4`. This is a second verified route into the same switch handler, independent of the KZB resource hook.

### What is and is not established

**Established:** event kind 2/8/9 reaches a manager callback that calls virtual `+0x50`; the current view can receive the same event through `+0x4c`; a later second `+0x50` call may re-evaluate the requested view. The derived manager overrides the event callback and the switch implementation.

**Not yet established:** the specific source of requested startup IDs **174, 176, 177, 178** in the event payload or derived manager's state; a definitive visible sequence still requires tracing **`0x11a8bc`** (derived event handler) and **`0x11871c`** (derived view selection) to their numeric ID sources.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a96d0 --stop 0x6a9984
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a94f4 --stop 0x6a96d0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11a8bc --stop 0x11a9e0
```

## Derived ViewManager event preprocessor: startup-relevant state changes before base dispatch

The derived vtable `0x7bfaf0` supplies **`+0x2c -> 0x11a8bc`**, and this routine has now been disassembled end-to-end. It is the **derived event preprocessor**, not merely another independent view-switch callback. At **`0x11ac34–0x11ac40`** it explicitly delegates to **base event handler `0x6a96d0`**, which performs the two virtual `+0x50` switch evaluations documented above. Therefore the actual application-owned pipeline is:

```text
derived ViewManager event +0x2c (0x11a8bc)
  -> handle mode-specific events and update ViewManager state
  -> base event handler 0x6a96d0
       -> virtual +0x50 (derived 0x11a250)
       -> current view virtual +0x4c, if applicable
       -> optional queued-event processing
       -> virtual +0x50 again
```

**Branch constraint:** this delegation occurs on the ordinary path. The derived preprocessor has at least one early-return path at **`0x11a9fc–0x11aa00`**, so not every recognized event necessarily reaches the base handler.

### Derived event gates

- At **`0x11a8f0–0x11a8f8`**, the preprocessor checks **`this+0x25`**. If zero, it jumps directly to base delegation. The specialized handling below is therefore conditional on this flag.
- For **kind 9**, it calls GTF2 `0x6aa348` to validate the event record before reading **`[event+4]`** as an ID (`0x11a91c–0x11a930`). Recognized event IDs include **22, 23, 40, 41, 42, 43, 344, 426, 429, 430, 434, 547, 548**. Their symbolic names are not established from these numeric comparisons alone.
- **Event 547** (literal `0x223`) sets **`this+0x88=1`** at **`0x11aab8–0x11aabc`**; **event 548** clears **`this+0x88=0`** at **`0x11aa94–0x11aaa0`**. This flag is the previously observed **needle-sweep / switch-suppression gate** checked at the beginning of derived `handleViewSwitch` (`0x11a2b8–0x11a324`). These events directly control whether a view transition may be deferred.
- **Events 40 and 41** call **`0x12b0d8`** with mode argument **1** and **0**, respectively (`0x11aa68–0x11aa74`, `0x11aa3c–0x11aa48`). The callee is GTF2-owned; its precise mode name remains to be proven.
- **Events 22, 23, 42, 43, 426, 429, 430** route through **`0x12a0e0`** or **`0x12b0d8`**, using boolean mode arguments; do not interpret these as direct numeric view IDs.
- For **kind 2**, only a specific ID in **`[event+4]`** enters the specialized branch (`0x11aae4–0x11aaf0`). It calls **`0x14c990`** to derive a boolean from the event, then manages **`this+0x6c`** and calls GTF2 `0x12a348` / `0x12ae14` (`0x11ab14–0x11abe4`). This is a concrete **DP-driven state transition** before the base view handler.
- For **kind 8 / subtype 16** (`[event+0xc]==16`), it invokes **`0x12b2f8`** (`0x11ac04–0x11ac30`) before base delegation.

### Derived view selection, verified boundary

The derived manager's virtual **`+0x58 -> 0x11871c`** checks `this+0x25` and `this+0x26`. If either is set, it writes **the current `this+0x1c` ID** to the output pointer and calls provider lookup **`0x6a9e9c`** with that ID (`0x11873c–0x118748`). Otherwise it tail-calls base selector **`0x6a8d5c`**. Thus **`+0x25/+0x26` gate which source of the view ID is used**; they are not themselves numeric view IDs.

**Emulation consequence:** events **547/548** and **kind 8 subtype 16** can change transition behavior even without a new explicit screen ID in the same event. Startup sequencing must model these state updates before evaluating the view switch. The named cluster startup IDs **174/176/177/178** have **not** been observed as constants in this derived event preprocessor, so do not infer a hardcoded cluster screen order here.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11a8bc --stop 0x11ac4c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11871c --stop 0x118750
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11a250 --stop 0x11a324
```

## Derived event-state helpers resolved: popup state machine, not direct startup view IDs

Disassembly of the three GTF2-owned callees used by derived `ViewManager` event preprocessing establishes that they update **a separate popup/transition state object**, rather than directly selecting cluster view IDs 174/176/177/178.

### Common state object and initializer

**`0x12a77c`** is a lazy singleton accessor: it returns **`0xab5d3c`** (`0x12a7c0–0x12a7c4`), using guard **`0xab5cf4`**. Its initialization path invokes **`0x12a18c`** (`0x12a7a0–0x12a7a4`).

The initializer **`0x12a18c`** writes a concrete default layout:

| State field | Initialized value |
| --- | --- |
| `+0x00` | 0 |
| `+0x18` | 0 |
| `+0x1c` | 2 |
| `+0x20` | 2 |
| `+0x24` | 0 |
| `+0x2c` | 2 |
| `+0x28` | 7 |
| `+0x34` | 3 |
| `+0x38` | 1 |
| `+0x39` | 0 |
| `+0x3a` | 0 |
| `+0x3b` | 1 |
| `+0x40` | 1 |
| `+0x41` | 0 |

These offsets belong to **the popup state singleton**, **not** the ViewManager object whose `+0x25/+0x26/+0x88` fields were discussed earlier.

### `0x12a0e0`: toggle a state byte, not an ID lookup

The function accepts `r0=state`, `r1=boolean/mode`; it compares **`state+0x3b`** with `r1` (`0x12a10c–0x12a114`). On change it writes **`state+0x3b=r1`** at `0x12a144` and tail-calls GTF2 function **`0x12a02c`**. There is no provider lookup and no literal startup view ID in this routine.

### `0x12b0d8`: guarded request, status return, state fields and action dispatch

This function accepts `r0=state`, `r1=requested mode`, `r2=auxiliary argument`:

1. It checks **`state+0x31`** at `0x12b10c–0x12b114`. If zero, it returns **0**.
2. Calls GTF2 **`0x12997c`** and admits status values **1 or 2**, or **5 with requested mode 0** (`0x12b118–0x12b140`). Rejected requests return **0**.
3. On acceptance, stores **`state+0x34=0`** and **`state+0x2c=requested mode`** at `0x12b168–0x12b170`.
4. Calls **`0x12a92c(state,requested_mode,aux)`** at `0x12b190–0x12b19c`, then returns **1**.

The requested mode is **not proven to be a view ID**. It is a state-machine request. This explains why derived event IDs 40/41 can call this function with arguments 1/0 without requesting screen IDs 1/0.

### `0x12a92c`: queued mode transition and an internal event 149/150

The callee first checks `state+0x31`; when unavailable, it sets **`state+0x34=3`** and returns (`0x12a964–0x12a970`, `0x12ab58`). If the requested mode differs from **`state+0x1c`**, it writes the requested mode into **`state+0x20`** (`0x12a974–0x12a988`). It has additional guards on `+0x38`, `+0x00`, `+0x39`, and `+0x32` that can defer the operation.

On the active path it writes **`state+0x1c=requested mode`** (`0x12aa18–0x12aa1c`), calls GTF2 animation/action function **`0x11f930`** (`0x12aa70–0x12aa94`), then constructs an event-like record and invokes an indirect callback at **`0x12aad0`**. The record carries **ID 149 if requested mode is nonzero, or 150 if zero** (`0x12aa98–0x12aad0`), with kind **9** written at `0x12aab4–0x12aabc`. These are **internal event IDs**, not provider view IDs: their numerical overlap with factory IDs is coincidental unless a consumer proves otherwise.

The same routine sets **`state+0x34=3`** on completion (`0x12aad4–0x12aae4`). This is a concrete state-transition path that can subsequently affect the ViewManager's view-switch timing.

### `0x12b2f8`: subtype-16 reset and three-way state dispatch

For the previously identified **event kind 8, subtype 16**, derived ViewManager calls `0x12b2f8`. This function:

- Gets the state singleton through **`0x12a77c`**.
- Clears **`state+0x39=0`** and sets **`state+0x32=1`** (`0x12b324–0x12b338`).
- If **`state+0x00==0`**, returns immediately (`0x12b340–0x12b348`).
- Otherwise branches on **`state+0x34`**:
  - **0**: calls **`0x12b0d8`** using the cached `state+0x2c` and an auxiliary pointer derived from the GTF2 manager (`0x12b36c–0x12b390`).
  - **1**: calls **`0x12ab84`** (`0x12b398–0x12b3b0`).
  - **2**: calls **`0x12acf0`** (`0x12b3b8–0x12b3d0`).
- For every non-early-return branch, sets **`state+0x34=3`** (`0x12b3d4–0x12b3dc`).

**Implication for emulation:** an event can change **pending transition state and internal event emission** without directly supplying a screen ID. Preserve the two layers: **ViewManager state** and this **GTF2 popup/action singleton**. A startup screen timeline still requires tracing which upstream event or DP value selects **174/176/177/178**; these helpers do **not** provide that selection.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12a0e0 --stop 0x12a168
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12a18c --stop 0x12a23c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12a77c --stop 0x12a7d8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12a92c --stop 0x12ab84
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12b0d8 --stop 0x12b1c0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12b2f8 --stop 0x12b3e4
```

## Actual view-ID source narrowed to a state record at BaseViewManager+0x08

The view-selection virtual **`+0x58`** has two confirmed implementations. Disassembly establishes the exact **non-popup/base-mode source of the numeric ID**, rather than merely showing another provider lookup.

### Base selector `0x6a8d5c`

At **`0x6a8d88–0x6a8da0`**:

```text
state = *(this + 0x08)
if state != NULL:
    id = gtf2_0x69d820(state)
else:
    id = 0
*output_id = id
return provider_getView(id)       # tail branch to 0x6a9e9c
```

The GTF2-local getter **`0x69d820`** is only three data operations:

```text
flags = *(uint32_t *)(state + 0x10)
if (flags & 1) != 0:
    return 0
return *(uint32_t *)(state + 0x14)
```

Thus **the actual requested view ID in base mode comes from `state+0x14`**, provided bit **0** of `state+0x10` is clear. A set bit forces **ID 0** (null view). This is a precise and testable **state → view ID → provider object** link.

### Derived selector `0x11871c`

At **`0x11871c–0x11874c`**, the derived ViewManager:

- If **`this+0x25 != 0`** or **`this+0x26 != 0`**, uses its **cached `this+0x1c`** as the output ID and calls the provider directly (`0x11873c–0x118748`).
- If **both flags are zero**, tail-calls base selector `0x6a8d5c`, which obtains the ID from the state record above.

This explains an important transition behavior: in the specialized mode, the derived manager can **retain the current ID** even when the underlying state record changes; when specialized mode ends, the selector again follows **`state+0x14`**. The observed code does not yet establish which event or setter writes startup IDs **174/176/177/178** into that field.

### Emulation-oriented pseudocode

```python
def selected_view_id(manager):
    if manager.flag_25 or manager.flag_26:
        return manager.cached_view_id_1c
    state = manager.state_ptr_08
    if state is None or (state.flags_10 & 1):
        return 0
    return state.view_id_14
```

This function represents **selection**, not resource preparation or guaranteed visible display. It should be evaluated through the previously documented event → virtual `+0x50` pipeline, respecting transition gates.

**Next trace:** locate the GTF2-owned writers of **`state+0x14`** and the bit-0 toggle at **`state+0x10`**. This is now the shortest path to proving which startup events request **174/176/177/178**, rather than inferring screen order from KZB load order.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a8d5c --stop 0x6a8dac
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d820 --stop 0x69d834
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x11871c --stop 0x118750
```

## State view-ID writer identified: conditional setter and five concrete callsites

The direct writer of the state record's **`+0x14` view ID** is **`0x69d810`**, immediately adjacent to the previously established selector getter `0x69d820`. These are short GTF2-owned functions, so their exact behavior can be expressed without symbolic guesses:

```c
void state_set_id(State *s, uint32_t id) {  // 0x69d810
    if (s->flags_10 & 0x6)
        s->id_14 = id;
}
uint32_t state_selected_id(State *s) {     // 0x69d820
    return (s->flags_10 & 1) ? 0 : s->id_14;
}
uint32_t state_candidate_id(State *s) {    // 0x69d7f0
    return (s->flags_10 & 1) && (s->flags_10 & 0x6)
           ? s->id_14 : 0;
}
```

**Important distinction:** the setter requires **bit 1 or bit 2** (`flags & 0x6`), while the view-selection getter requires **bit 0 clear**. These are **independent gates**. The separate `0x69d7f0` candidate getter requires **bit 0 set AND at least one of bits 1/2 set**; it is not equivalent to the selection getter. Avoid modeling all three as a single boolean `view_active` flag.

### Five direct callers of the setter

A complete ARM BL scan of the executable PT_LOAD found exactly **five** direct calls to `0x69d810`:

| Callsite | GTF2-owned caller path | Value written |
| --- | --- | --- |
| **`0x69c8f8`** | list/tree synchronization in `0x69c7bc–0x69c974` | **`[r5+0x00]`** (ID from a source record) |
| **`0x69c958`** | same synchronization loop | **`[r2+0x00]`** (ID from another source record) |
| **`0x6ac258`** | index/range maintenance in `0x6ac208–0x6ac398` | literal **0** |
| **`0x6ac2d8`** | same range-maintenance routine | literal **0** |
| **`0x6ac374`** | same range-maintenance routine | literal **0** |

At **`0x69c8f0–0x69c8f8`**, the first synchronization path loads `r1=[r5]` and passes `r0=r6` to the setter. At **`0x69c94c–0x69c958`**, the second path loads `r2=[sp+0x18]`, then `r1=[r2]` and again passes `r0=r6`. Thus **the nonzero requested ID is copied from a source record**, not generated as a hardcoded constant at the setter callsite.

The three `0x6ac2xx` calls all explicitly load **`r1=0`** before calling the setter; they are **clear/reset paths** that can invalidate a view selection when range/list entries change. These calls are conditional on record-state tests involving GTF2 helpers `0x69d864` and `0x69d870`; they are **not** unconditional clears.

### Consequence: view IDs are data-driven

The actual GTF2 view selection now has an explicit producer-consumer chain:

```text
source record ID ([record+0x00])
  -> synchronization 0x69c8f8 / 0x69c958
  -> state_set_id 0x69d810, conditional on flags & 0x6
  -> state+0x14
  -> state_selected_id 0x69d820, conditional on !(flags & 1)
  -> BaseViewManager selector 0x6a8d5c
  -> provider getView(id)
  -> derived handleViewSwitch +0x50, subject to transition gates
```

The producer is a **record list/tree**, so a startup view ID may originate from an **upstream state record**, not from a literal `mov r1,#174` near `ViewManager`. This is a useful constraint on the remaining reverse engineering: trace construction and updates of **source record `+0x00`** and the list synchronization function rather than scanning only for startup ID constants.

The five calls above are a **direct BL census**; additional inlined writes or indirect calls have not been excluded. The list structure's exact semantic name is still unknown.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/trace_view_id_state_writers.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d7f0 --stop 0x69d834
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69c7bc --stop 0x69c974
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6ac208 --stop 0x6ac398
```

## Upstream record source resolved: 32-byte indexed records and a linked ID chain

Direct disassembly of **`0x69c68c–0x69cbcc`** and **`0x6ac100–0x6ac204`** reveals the data structures supplying the view ID to the conditional setter. This narrows the producer beyond the earlier generic “list/tree” description.

### Indexed record lookup `0x6ac100`

The routine takes `r0=indexed_container`, `r1=record_id` and checks:

1. `record_id != 0` and `container->records_00 != NULL`.
2. `record_id < container->count_04` (unsigned).
3. Calculates **`record = records_00 + (record_id << 5)`**, i.e. a **32-byte record stride** (`0x6ac12c–0x6ac130`).
4. Requires **`record->id_00 == record_id`** (`0x6ac134–0x6ac138`), otherwise logs a mismatch at `0x6ac13c–0x6ac160` and returns null.

The exact ID-indexed record layout confirmed from callers is:

```c
struct IndexedRecord {           // 32-byte stride, not complete field naming
    uint32_t id_00;              // self-ID, must match array index
    uint32_t next_id_04;         // linked-chain successor
    uint8_t unknown_08[8];
    uint32_t flags_10;           // gates view-ID read/write and callbacks
    uint32_t selected_id_14;     // conditional view ID
    uint32_t callback_18;        // used when flags & 0x40
    uint32_t callback_1c;        // used when flags & 0x20
};
```

The **`next_id_04`** interpretation is directly supported by `0x69c790–0x69c7b8`: the synchronization routine reads **`[record+4]`**, appends that value to a temporary list, and calls **`0x6ac100(container, next_id)`** to walk to the next record. It stops at a zero successor or an invalid lookup.

### Synchronization entry `0x69c68c`

At function entry:

- `r0` points to a small manager record that holds the indexed container at **`[r0]`**.
- `r1` is a requested starting ID; `r2` and `r3` supply additional context.
- It reads **`container->selected_id_14`** from the object referenced by **`[r0]`** at **`0x69c6a8–0x69c6b0`**. This is a distinct field from the **individual 32-byte record's `selected_id_14`** and should not be merged into one state variable.
- At `0x69c77c–0x69c7b8`, it builds an ordered chain of IDs by following `next_id_04`, using `0x6ac100` for every link.
- At `0x69c884–0x69c8f8`, it resolves a destination record via **`0x6ac100(container, source->next_id_04)`**, then conditionally copies **`source->id_00`** into **`destination->selected_id_14`** via `0x69d810`.
- The companion path at `0x69c94c–0x69c958` copies another saved chain ID into that same destination field.

Therefore **`selected_id_14` can be the ID of an adjacent/previous chain record**, not necessarily the destination record's own `id_00`. This explains why the base selector reads `selected_id_14` instead of returning the record's self-ID.

### Structural checks and clear paths

`0x6ac184` validates that one ID is reachable from another by repeatedly following **`next_id_04`** through `0x6ac100`; it terminates on null, a matching successor, or an invalid lookup. The separate `0x6ac208` routine traverses record IDs and conditionally resets **`selected_id_14=0`** via the three known `0x69d810` callsites.

The view-selection state is therefore a **validated, ID-indexed, singly linked record graph**, not a flat array of screen IDs or a static switch statement. Its **32-byte record stride** is a useful QEMU inspection target and can be verified against a runtime memory dump without reverse-engineering external libraries.

### Limits and next boundary

The disassembly establishes the **layout and propagation algorithm**, but does **not** establish who initially populates the 32-byte records with IDs **174, 176, 177, 178**. Those numeric IDs are currently proven in the **view factory and KZB resource-preparation calls**, not in this record graph. The next trace is **writes to `IndexedRecord.id_00` and `next_id_04`**, and the caller chain into **`0x69c68c`**.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6ac100 --stop 0x6ac208
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69c68c --stop 0x69c974
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d7b0 --stop 0x69d878
```

## Two callers of chain synchronization found; source ID is a requested record, not a hardcoded startup constant

A full direct ARM BL census of the executable found exactly **two** callsites of **`0x69c68c`**, both in the same GTF2-owned surrounding routine:

| Callsite | Inputs reconstructed | Follow-up |
| --- | --- | --- |
| **`0x69cca8`** | `r0=r6` manager, `r1=r7` requested ID, `r2=r5` result of `0x6ac100([r6], [r4+8])`, `r3=r4` source object | `0x69ccac–0x69ccc8` converts result to boolean and updates current selection with `0x69c64c` |
| **`0x69d068`** | `r0=r6` manager, `r1=r5` requested record, `r2=r8` alternative resolved record, `r3=r4` source object | `0x69d06c–0x69d088` again calls `0x69c64c` with selected record ID |

At **`0x69cc74–0x69cc80`**, the first path explicitly reads **`[r4+8]`**, then resolves that value through the **32-byte record array**. The selected ID is therefore carried through a **source object's field at `+0x08`**, rather than being an immediate constant at the synchronization call.

At **`0x69d000–0x69d008`**, the second path updates a record's **`next_id_04`** and calls **`0x69d84c`**, which sets or clears **bit 4 (`0x10`)** of its `flags_10`. This is a **separate flag** from the bit-0 read gate and bits-1/2 write gate, so it must not be conflated with the view-selection block.

The verified chain now spans:

```text
source object's requested ID at +0x08
  -> indexed record lookup 0x6ac100
  -> chain synchronization 0x69c68c (two direct callers)
  -> conditional selected_id_14 writes 0x69d810
  -> BaseViewManager selector 0x6a8d5c
  -> provider factory
  -> event-driven virtual switch handler
```

The **precise upstream writer of the source object's `+0x08`** and the initial contents of the 32-byte record array remain unknown. No evidence yet proves that this source emits startup IDs **174/176/177/178**. This is the next boundary for tracing, not an excuse to infer the visible startup order.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69cc48 --stop 0x69ccd0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69cfdc --stop 0x69d08c
```

## Upstream dispatcher found: record-chain synchronization is event-driven

Disassembly of the direct callers above `0x69cbf0` establishes another full application-owned layer above the indexed record graph. **`0x69d19c`** is an event-processing entry; it calls GTF2 classifier **`0x6ac3f8`** and conditionally forwards to the record synchronization machinery.

### `0x69d19c`: event classification and conditional record update

- **`0x69d1ec–0x69d1f4`** reads **`[event+0x00]`** and explicitly compares it to **9**. Thus the handler consumes a record with the same event-kind convention as the manager event pipeline. This does **not** prove every event kind 9 reaches this handler.
- At **`0x69d214–0x69d22c`**, it calls **`0x6ac3f8(container, auxiliary, event, &local, extra)`**.
- At **`0x69d230–0x69d238`**, a classifier result of **2** takes a special path; otherwise **`0x69d288–0x69d298`** forwards to **`0x69cbf0`**, which contains the two previously mapped calls to **`0x69c68c`**.
- The wrapper checks the result of `0x69cbf0` at **`0x69d29c–0x69d2a4`** and returns the resulting status code. Therefore a single incoming event may be classified as a special case, rejected, or passed through to record-chain synchronization.

### `0x69cbf0`: source record and status-dependent behavior

The wrapper accepts **`r0=record_manager`**, **`r1=source`**, **`r2=event/context`**, **`r3=extra`**. Its first path:

1. Calls GTF2 `0x754bd8` to validate the manager/container (`0x69cc08–0x69cc20`).
2. Checks **bit 9 (`0x200`) of `[source+0x00]`** (`0x69cc24–0x69cc38`). On that path it clears a byte at **`manager+0x08`** and exits with status **1**; otherwise it continues.
3. Reads **`source+0x08`** and calls indexed-record lookup **`0x6ac100`** (`0x69cc74–0x69cc80`).
4. Passes the resulting record and original source to **`0x69c68c`** (`0x69cc84–0x69cca8`), then invokes `0x69c64c` to update the manager's cached selection pointer (`0x69ccac–0x69ccc8`).

**Important correction:** **`0x69c64c` writes `manager+0x04` as a pointer to a validated record**; it does **not** write a view ID directly. The **ID write** remains the separate `0x69d810` setter into the selected 32-byte record's **`+0x14`** field.

### `0x69d0cc` and `0x69d12c`: wrapper and state gate

The compact wrapper **`0x69d0cc`** creates zeroed stack-local temporary records (16 bytes and 64 bytes), copies the incoming request into a local field, and invokes **`0x69cbf0`** at **`0x69d120`**. Its caller **`0x69d12c`** checks **`manager+0x0c`**: values **0 or 2** permit this wrapper path, then it writes **`manager+0x0c=1`** and tail-calls **`0x6ac3a8`**. Other values take a diagnostic/error path. This establishes an explicit **manager phase gate** around the record update.

### Updated verified pipeline

```text
GTF2 event record (kind 9 among possible kinds)
  -> 0x69d19c
  -> 0x6ac3f8 classification
       -> result == 2: special path
       -> other: 0x69cbf0 record event wrapper
           -> source+0x08 record ID
           -> 0x6ac100 validates 32-byte indexed record
           -> 0x69c68c synchronizes linked record IDs
           -> 0x69d810 conditionally writes record+0x14
           -> 0x69c64c caches validated current record pointer
  -> BaseViewManager +0x58 reads selected ID via 0x69d820
  -> provider getView(id)
  -> virtual +0x50 switch handler
```

**Do not assume this is a single synchronous call stack from event to rendered frame.** The event/record pipeline and manager's view-switch evaluation are separately invoked; the chain shows the verified **data dependency**. The event-to-record connection is now proven, but the exact **startup event payloads** selecting **174, 176, 177, 178** are still unknown.

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/trace_record_event_routes.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d19c --stop 0x69d2d0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69cbf0 --stop 0x69ccc8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d0cc --stop 0x69d168
```

## The previously missing link is inside BaseViewManager's event loop (verified)

Tracing **upward** from `0x69d19c` found **four** direct callsites, all inside three GTF2-owned queue-processing functions:

| Caller | Callsite(s) | Queue behavior |
| --- | --- | --- |
| `0x69d2d0` | **`0x69d3a8`** | Traverses the 32-byte linked record chain, gathers IDs satisfying `0x69d7e4` (bit-2 flag), calls per-record virtual callback `+0x0c` through `0x6a5d40`, and drains the event queue |
| `0x69d42c` | **`0x69d4a8`** | Repeatedly takes queue entries while manager phase is not 1 |
| `0x69d4c8` | **`0x69d50c`** | Performs queue drain, direct event classification, another drain, and optionally resets queue cursors |
| `0x69d5dc` | **`0x69d668`** | For manager phase 1, invokes reset wrapper and drains queue before leaving phase |

**The key connection is at `0x6a9894`:** `BaseViewManager` event callback **`0x6a96d0`** calls **`0x69d4c8(manager+4,event,aux)`** when the current view has been notified and a queued-state gate is satisfied. This directly connects the event manager to the record classifier **`0x6ac3f8`** and conditional view-ID writes, without hypothesizing an external callback.

Additional manager-owned routes:

- **`0x6a9380`** calls queue-drainer `0x69d42c` when `0x69c574(manager+4)` reports pending data.
- **`0x6a9048`** calls phase-1 queue-drainer `0x69d5dc`.
- **`0x6a8ee4`** calls `0x69d3d4`, a phase-gated wrapper around `0x69d2d0`.

### Queue layout and semantics

The queue resides in a container pointed to by **`[manager+4]`**. The helper **`0x6ac07c`** tests whether the queue is nonempty by comparing `queue+0x20`, `+0x24`, `+0x28`. The pop helper **`0x6ac0a8`** reads from an array pointer at **`queue+0x18`**, using index **`queue+0x20`**, then advances/wraps the cursor relative to **`queue+0x1c`** and resets it on reaching the producer cursor. The entry is a **32-bit pointer/value**; the exact ownership of the pointed-to event record remains to be established.

The queue-draining functions create stack-local event/auxiliary records before calling `0x69d19c`. Therefore **the classifier does not always receive the raw external event unmodified**; some calls receive synthetic or normalized records. In particular, the literal **9** placed in a stack local by the drainer is **not sufficient to assert a startup view ID of 9**.

### Full statically established dependency path

```text
derived manager event callback +0x2c (0x11a8bc)
    -> base event callback 0x6a96d0
       -> virtual +0x50 derived handleViewSwitch (pre-event)
       -> current view virtual +0x4c (event notification)
       -> queue drain 0x69d4c8 (call at 0x6a9894)
           -> 0x69d42c / 0x69d19c
              -> 0x6ac3f8 classifier (iterates 32-byte linked records)
              -> 0x69cbf0 (unless classifier returns 2)
                 -> 0x69c68c record-chain sync
                    -> 0x69d810 conditional record+0x14 ID setter
                 -> 0x69c64c current-record pointer update
       -> virtual +0x50 derived handleViewSwitch (post-event)
          -> +0x58 selector (0x11871c / base 0x6a8d5c)
             -> 0x69d820 read selected ID from record+0x14
             -> provider 0x6a9e9c / 0x25a940
          -> switch handshake, fade/transition and slot flush
```

**This closes the missing *static control-flow and data-flow path* from event reception through record updates to screen selection.** It is **not** proof that every event follows every branch, nor does it establish the **runtime startup order** of IDs **174/176/177/178**. Those IDs have been verified in the resource batches and view registry, but not as values of the runtime queue records. A concrete startup timeline requires a runtime trace of event payloads, queue entries and `record+0x14` updates (or equivalent initialization data).

### Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6a984c --stop 0x6a98b0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d2d0 --stop 0x69d3d4
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d42c --stop 0x69d590
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69d5dc --stop 0x69d680
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6ac07c --stop 0x6ac100
```

## Verification and remaining dynamic boundary

The committed **`verify_event_to_view_path.py`** checks **nine exact ARM BL edges** and **five vtable targets** directly against the original GTF2 ELF bytes. It fails nonzero if any expected edge is absent or differs. The verified vtable targets are `0x7bfb1c -> 0x11a8bc`, `0x7bfb40 -> 0x11a250`, `0x7bfb48 -> 0x11871c`, `0x891984 -> 0x6a96d0`, `0x8919a8 -> 0x6a91a8`.

```sh
python3 tools/fpk1/research/gtf2/verify_event_to_view_path.py /path/to/gtf2
```

**Static path completion criteria are met:** event callback, queue drain, record classification, chain synchronization, conditional ID setter, selector, factory, and virtual switch target are connected by exact instructions or vtable pointers. The resulting reconstruction is **conditional control flow**, not a guarantee that all stages run for every event.

**Dynamic startup chronology is a separate unresolved question.** To establish which of **174, 176, 177, 178** actually becomes visible and in what order, capture at least these five application-owned points in a running GTF2/QEMU session:

| Trace point | Capture |
| --- | --- |
| `0x6a96d0` / `0x11a8bc` | event kind `[r1]`, event ID `[r1+4]` where valid, current manager state |
| `0x69d19c` | record-manager pointer, event/aux arguments, classifier result at `0x69d230` |
| `0x69d810` | state pointer `r0`, proposed ID `r1`, `[r0+0x10]` mask, resulting `[r0+0x14]` |
| `0x11871c` / `0x6a8d5c` | selected ID, `+0x25/+0x26` gates and active record pointer |
| `0x11a250` / `0x119688` | requested ID, old/current ID, transition flags and actual commit of switch |

Because this is **ARM32 QNX** with a firmware-specific process environment, static analysis alone cannot supply the missing runtime event payloads or prove a visible-frame timeline. Do not fabricate that timeline from KZB resource request order. The above capture points are deliberately **inside GTF2**, avoiding external-library reverse engineering.

## GTF2 IPC surface: services, received signals and reactions

This section distinguishes **KSS↔Tegra transport** from the **GTF2 application-facing IPC**. Evidence: literal service names, method diagnostics and RTE callback diagnostics in the original GTF2 ELF, together with the separately reconstructed `gss_ipc` SPI protocol and QEMU runs in `docs/fpk1-firmware-research.md`. These are *application-owned integration points*, not a claim to have reverse-engineered the underlying comm libraries.

### Transport and activation boundary

```text
KSS MCU / vehicle CAN inputs
  -> KSS-to-Tegra SLINK1 SPI, 128-byte gss_ipc frames
  -> gss_ipc: RTE, mode/state management and service proxies
  -> local ASI IPC endpoints used by GTF2
       |-> asi.gss.manager.hmi.IGssMan2HMI (lifecycle)
       |-> asi.gss.ipc.rte.hmi.IHmiKss (vehicle and input events)
       |-> asi.gss.ipc.bap.IHmiBap (BAP)
       |-> asi.gss.ipc.ddt.IDdt (DDT)
  -> GTF2 DP/state and key-event handlers
  -> ViewManager / current views
```

The KSS-side **`GSS_MODE_REQUEST`** (CID 3) is decoded in **`gss_ipc`**, *not in GTF2*. As previously verified in the base firmware research, KSS application-run requests `GSS_MODE_REQUEST(1,2)` cause `gss_ipc` to request HMI startup through the local **`IGssMan2HMI`** service; GTF2's `GssMan2HMIReplyImpl::activate()` is the application-facing endpoint. `GSS_MODE_RESPONSE` is generated on the KSS-facing side. Do not conflate the SPI CID with a QNX message type or an event ID in GTF2.

### Confirmed application-facing services

| Service / implementation | ELF string address | Incoming or outgoing role and observed reactions |
| --- | --- | --- |
| `asi.gss.manager.hmi.IGssMan2HMI` | `0x88e2c4` | GSS manager → GTF2: `GssMan2HMIReplyImpl::activate()` (`0x88e28b`), `deactivate()` (`0x88e24c`), `enterColdCrank()` (`0x88e1d8`), `leaveColdCrank()` (`0x88e0cc`), `persistentData()` (`0x88e1b2`). |
| `asi.gss.manager.hmi.IGssMan2HMIReply` | `0x88e2e4` | Reply/proxy interface. Diagnostics show `coldCrankRep()`, `enterColdCrankRep()`, `leaveColdCrankRep()`, `persistentDataRep()`, plus `switchDisplayBacklight()` and `sendPersistentData()`; no assumption of uniform synchronous reply. |
| `asi.gss.ipc.rte.hmi.IHmiKss` | `0x88f55d` | KSS/RTE → GTF2: vehicle signal callbacks in `HmiCommKssReplyImpl`. Diagnostics show DP writes under `batchLock()`, list updates, timeout and not-initialized handling. |
| `asi.gss.ipc.rte.hmi.IHmiKssReply` | `0x88f579` | RTE service reply interface. Lost-server diagnostic `0x88f521`: `HmiCommKssReplyImpl lost server connection, reactivating...`. |
| `asi.gss.ipc.bap.IHmiBap` / `IHmiBapReply` | `0x88d879` / `0x88d891` | BAP channel. `HmiCommBapReplyImpl lost server connection, reactivating...` at `0x88d83d`. |
| `asi.gss.ipc.ddt.IDdt` | `0x88da1e` | DDT messaging: `DdtImpl::sendMessage(): message id=0x%04X` at `0x88d9c7`; reconnect diagnostic `0x88d990`. |
| `asi.gss.ipc.rte.hmi.IHmiKss` keyboard conversion | `0x7d9959` / `0x7da247` | `GSS_APP_KeyEventConverter::handleKeyEventMfl` accepts **four parameters** (keycode1, eventcode1, keycode2, eventcode2), translates through an MFL mapping table into HMI event ID/ticks. |
| `asi.diagnosis.gss2app.GSS2AppDtcTestService` / `Reply` | `0x88dd10` / `0x88dd3c` | Diagnosis: `activate`, `deactivate`, `alive`, `dead`, `performTest`, `performAllTests`, `setDtc`, `testStatus`. |
| `asi.gss.manager.IAlive` / `IAliveReply` | `0x890156` / `0x89016d` | Local alive supervision interface. Distinct from the KSS-facing SPI `GSS_ALIVE_REQUEST` CID 11. |
| `asi.gss.ipc.rte.hmi.IHmiKss` and capture/diagnostics | `0x88f853`, `0x88faf9` | `GSS_HMI_GTF2_CapturingReplyImpl` handles capture state/lock pin; `GSS_IPC_GSS2GTFDiagService` handles adaptation channels `0x518`, `0x523` (files `adaption/chan_0518.bin`, `adaption/chan_0523.bin`). |

**Caution:** names ending `Reply` reflect the service/proxy nomenclature, not necessarily a distinct network connection or a proven wire response. Exact ASI method numbers, marshalled arguments, channel IDs and QNX transport primitive still require interface/registration-code inspection.

### RTE signal callbacks present in GTF2

The following strings are **concrete callback names in the GTF2 executable**, not guessed from generic automotive CAN naming. A callback name proves that GTF2 has a handler; it does **not** prove the signal is transmitted in every vehicle variant.

| Category | Callback names in `HmiCommKssReplyImpl` | Application reaction visible in diagnostics |
| --- | --- | --- |
| Power / startup | `ClampS`, `Clamp15`, `Systeminfo01`, `Config_Coding`, `Config_Installation_Coding` | Clamp values logged (`0x88f46e`); config/status data updates via DP batches |
| Engine / hybrid | `TCH_HMI_EngineRPM`, `BMS_10`, `Motor_Hybrid_03_MO_Powermeter`, `Motor_Hybrid_06`, `HMI_EngineID_MKB`, `HMI_Motor_26` | Batch DP updates, not direct calls to `ViewManager::doSwitch` |
| Vehicle state | `Gear_Display`, `Gear_Display02`, `ODO_HMI_Distance`, `Tank_IndicationVolume`, `HVK_01`, `CarOutline_HMI` | Gear, odometer, fuel and door/outline model data |
| Driver assistance | `ACC_02`, `ACC_12`, `ACC_14`, `ACC_HMI_Display`, `GSS_ACC_Display_Status`, `VZE_01`, `HMI_C_NightVision_Display`, `Config_Driverassist_Media` | HMI/DP updates; ACC callback logs dispatch to `Kombi_01` and discards when proxy is not alive (`0x88ee68`, `0x88ee90`) |
| Warnings / telltales | `TelltaleAALA_Display`, `TelltaleHMI_Blink`, `TelltaleHMI_Display`, `KombiDef`, `ZPM_HMI_Info`, `ActTest_SoftLEDs`, `ActTest_CommonSoftLEDs` | Warning/telltale data written into DP; ZPM diagnostic logs warning ID and popup ID (`0x88f33c`) |
| Other vehicle data | `NVEM_02`, `TSK_07`, `DS_VCM_DisplayArea`, `Config_Antrieb`, `Config_View_Specifica`, `FanControl`, `BC_HMI_E_CurrentConsRecu`, `ECT_HMI_Information` | Batch DP updates |
| Input events | `MFL_Tasten_Kon_01` (upstream RTE signal), MMI CAN key, joystick and touchpad messages | `handleKeyEventMfl` / `handleKeyEventMmi`; conversion to event IDs, rotary ticks, HMI/telephone/warning/engineering menu routes |

Most of these handlers have literal `batchLock() failed` diagnostics in **`0x88ef3e–0x88f4eb`**, which strongly supports a **signal → DP batch → HMI state/view update** pattern. The exact per-field DP IDs and values require disassembling each callback; do not infer that every incoming signal causes a view switch.

### Key and event-specific reactions

- **MFL steering wheel**: `handleKeyEventMfl(keycode1,eventcode1,keycode2,eventcode2)` at diagnostic `0x7d9959`. `detectMflKeyCombination` may consume the input first (`0x7d99b3`). Otherwise keycodes are looked up and logged as **`idx,is_but,ev_id,ticks`** (`0x7da247`); unknown keycodes and wheel event codes are discarded (`0x7da225`, `0x7da291`). Rotary wheel can inject a separate event (`0x7d9a17`).
- **MMI CAN key/joystick/touchpad**: `handleKeyEventMmi` (`0x7d986e`); parsing diagnostics at `0x7d9d40–0x7da1fb` include protocol byte validation, keycode/event mapping, joystick IDs, rotary ticks and touchpad finger coordinates, with bounds clamping.
- **TWS reset / version screen**: `handleKeyEventTws` (`0x7d957e`) checks HMI readiness and tube visibility (`0x7d960e`); diagnostics distinguish short/long reset, restore, and version-screen timers (`0x7d9655–0x7d9843`).
- **Application event dispatcher**: kind **2** carries DP changes, kind **8** HMI/internal subtypes (including language, rendering gates, popup hidden), kind **9** application events (including frame 284, skin switch 500, needle-sweep gates 547/548). These are **post-IPC HMI event kinds**, not SPI CIDs.
- **Cold crank**: `enterColdCrank()` logs “Entering critical undervoltage” (`0x88e1fe`); `leaveColdCrank()` logs “Leaving critical undervoltage” (`0x88e0f2`). Their downstream state changes should be traced before asserting exact display brightness or rendering side effects.
- **RTE errors**: `HmiCommKssReplyImpl rteNoInit %d` (`0x88ec08`), `rteTimeout %d` (`0x88eed4`), lost server reconnect (`0x88f521`).

### Verification and scope

Run `python3 tools/fpk1/research/gtf2/inventory_ipc_handlers.py /path/to/gtf2` to print the exact ELF string addresses. The SPI framing, KSS mode request/response, MFL RTE bridge and working `kss_peer.py` are documented in `docs/fpk1-firmware-research.md` and should not be conflated with the local ASI IPC layer.

**Remaining for a byte-exact IPC emulator:** trace the GTF2-owned ASI registration/vtable dispatch and per-method argument layout; recover the full MFL keycode mapping table and DP-ID mappings for individual `IHmiKss` callbacks; compare against runtime logs. The service and signal inventory above is concrete, but is not yet a byte-level reimplementation of every IPC interface.

### Exact MFL keycode → GTF2 event-ID table recovered

The GTF2-owned mapper **`0x18c82c–0x18c98c`** uses three fixed data tables:

- **`0x7da8a4`**: 36 × `uint32_t` mapping external **keycode 0–35** to internal index **0–16**; index **16** is the invalid sentinel.
- **`0x7d9d30`**: 16 × `uint8_t` button/rotary classifier; **index 8** is the non-button (rotary) entry.
- **`0x7da5a8`**: 16 rows × 6 `uint32_t` HMI event IDs, with **`0xffffffff`** as no-event sentinel. The lookup uses event-code positions 1–6. For buttons, event codes **1 and 3** produce the same event ID, **4** generally produces a different one, and **2, 5, 6** are unmapped. Key index **8** is handled by the separate wheel-tick path, not by this matrix.

| Incoming MFL keycode | Internal index | HMI event ID for eventcode 1/3 | HMI event ID for eventcode 4 |
| ---: | ---: | ---: | ---: |
| 1 | 1 | 495 | 494 |
| 2 | 2 | 444 | 441 |
| 3 | 3 | 439 | 438 |
| 7 | 9 | 473 | 470 |
| 8 | 4 | 447 | 446 |
| 9 | 5 | 465 | 464 |
| 10 | 6 | 483 | 482 |
| 11 | 7 | 486 | 485 |
| 19 | 10 | 498 | 497 |
| 25 | 11 | 477 | 476 |
| 28 | 15 | 479 | 478 |
| 32 | 12 | 468 | 467 |
| 33 | 13 | 450 | 449 |
| 35 | 14 | 495 | 494 |

**Keycode 6** maps to **index 8 (rotary)** and is processed via signed ticks for eventcodes in the mapper's accepted range; its six matrix entries are all invalid. **Keycode 0** maps to index 0, whose event matrix entries are all invalid. All other keycodes in **0–35** map to sentinel index 16; values **greater than 35** also take the invalid path. This is the numeric translation only; semantic button labels (OK, BACK, etc.) are **not** assigned without additional proof.

The table is **directly extracted from the original ELF**, not inferred from a list of expected buttons. Reproduce with:

```sh
python3 tools/fpk1/research/gtf2/decode_mfl_keymap.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x18c82c --stop 0x18c9ac
```

For a KSS peer or input simulator, this establishes the application-side **keycode/eventcode → HMI event ID** mapping, while the exact KSS-to-`gss_ipc` RTE wire record remains a separate transport question.

### RTE callback → exact DP-ID mapping: first byte-level examples

Disassembly now ties named `IHmiKss` callbacks to **concrete data-pool IDs and payload offsets**, not just callback strings. The ARM routines first obtain a DP batch lock (`0x130b4c`), call `0x131390` with each **DP ID in r1** and **payload value in r2**, then release the batch (`0x1309ac`). These are GTF2-owned callback instructions; the data-pool library internals need not be reversed.

**`TCH_HMI_EngineRPM` at `0x697264`:**

| Incoming payload | Width | GTF2 DP ID | Evidence |
| --- | --- | --- | --- |
| `payload+0x00` | little-endian `uint16_t` | **`0x02000293`** | `0x697290–0x697298` |
| `payload+0x02` | little-endian `uint16_t` | **`0x02000295`** | `0x6972a4–0x6972ac` |

Both writes are conditional on successfully acquiring a **two-item batch**. A failed lock takes a diagnostic path and does not execute these two `0x131390` calls. Following the batch, the callback calls additional GTF2 functions `0x151558`, `0x14ebf8` and `0x1de81c`; their side effects are not yet classified.

**`Gear_Display` at `0x69534c`:** it obtains a **12-item batch** and maps **12 byte offsets** from the incoming payload to exact DP IDs:

| Incoming byte offset | DP ID | Incoming byte offset | DP ID |
| ---: | --- | ---: | --- |
| `+0x00` | `0x020001f7` | `+0x01` | `0x020001f5` |
| `+0x02` | `0x020001fc` | `+0x03` | `0x020001f6` |
| `+0x04` | `0x020001fa` | `+0x05` | `0x020001f8` |
| `+0x06` | `0x020001fd` | `+0x07` | `0x020001fb` |
| `+0x0a` | `0x020001ef` | `+0x09` | `0x020001ec` |
| `+0x08` | `0x020001ee` | `+0x0b` | `0x020001f9` |

The 12-item batch corresponds to **12 actual `uint8_t` fields**, including `payload+0x0b` → `0x020001f9` at `0x695450–0x695458`. The callback ends by releasing the batch via `0x1309ac`. The byte offsets are not in ascending order in the compiled code (`+0x0a` precedes `+0x09` and `+0x08`).

These two callbacks demonstrate a reproducible path:

```text
KSS CAN/RTE record
  -> gss_ipc local IHmiKss service
  -> GTF2 HmiCommKssReplyImpl callback
  -> payload field read (u8/u16)
  -> DP ID passed to 0x131390
  -> DP change events (kind 2) and subscribed view handlers
  -> ViewManager event/selection logic where applicable
```

The last two arrows represent the **previously recovered downstream DP event mechanism**, not proof that either gear or RPM update necessarily changes the visible screen. This is the correct boundary for interpreting “which IPC signal causes which reaction.”

To reproduce exact numeric fields (the script validates each literal-load instruction and each payload-load instruction):

```sh
python3 tools/fpk1/research/gtf2/decode_rte_dp_fields.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69534c --stop 0x6954cc
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x697264 --stop 0x697310
```

### Automated scan of direct RTE payload-to-DP writes (176 sites)

A conservative ARM32 static scanner over the GTF2-owned callback code range `0x680000–0x6a0000` identifies **176 distinct call sites** to the DP setter `0x131390` where:

1. The call is a direct ARM `BL` to `0x131390`.
2. The immediately preceding code loads **r1** with a PC-relative 32-bit literal DP ID whose top byte is `0x02`.
3. The same short instruction sequence loads **r2** using a direct `LDRB` or `LDRH` field read from the incoming payload.

Reproduce against the original extracted GTF2 ELF:

```sh
python3 tools/fpk1/research/gtf2/scan_rte_dp_writes.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-ipc-dp-fields.csv
```

The **176** figure counts instruction-level field-to-DP write sites, **not** 176 different incoming CAN signals or 176 unique DP IDs. The matches are clustered across code pages: **47** in `0x694000–0x694fff`, **80** in `0x695000–0x695fff`, **40** in `0x696000–0x696fff`, and **9** in `0x697000–0x697fff`. Other callbacks may write through computed values, use non-literal IDs or call wrappers and therefore are intentionally absent.

The scan exposed and corrected a previous documentation omission: **`Gear_Display` writes 12 bytes**, including the last `payload+0x0b` → `0x020001f9` mapping at `0x695450–0x695458`. A 12-item batch is therefore consistent with 12 actual direct writes. This is verified from the ARM disassembly, not inferred from the batch count.

**Interpretation boundary:** this identifies how GTF2 maps payload fields into DP state. It does not by itself establish the corresponding SPI LUN/record layout or whether the values are subsequently used to switch views. The next stage is associating each callback entry with its `IHmiKss` service method and tracing its downstream DP consumers.

### Grouping field writes by GTF2-owned callback function

The 176 field-to-DP write sites are now grouped by their nearest preceding ARM `push {...,lr}` function prologue. This yields **45 candidate callback functions** in the `0x694000–0x697fff` code region. Each group retains the exact call address, payload offset, width and DP ID, and is exportable as a CSV for later association with the corresponding `IHmiKss` method/vtable.

```sh
python3 tools/fpk1/research/gtf2/group_rte_dp_callbacks.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/group_rte_dp_callbacks.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-ipc-dp-by-callback.csv
```

For example, the scanner groups the **12 Gear_Display** direct writes under function prologue **`0x695348`** and the **2 TCH_HMI_EngineRPM** direct writes under **`0x697264`**. This is a grouping of **instruction-level sites**, not a claim that GTF2 has only 45 IPC callbacks: other callbacks can update DP via transformed values, wrappers or different call patterns.

**Validation:** executed the direct ARM scan against the original 10,180,269-byte GTF2 ELF locally and reproduced **176** matches, **176 distinct DP-ID values**, distributed across **45** candidate functions. Function grouping uses a heuristic prologue scan and must be cross-checked against service vtables before treating every candidate boundary as a named interface method.

The follow-on task is the `IHmiKss` service method index → callback address mapping; the existing callback diagnostics are not sufficient to assign all 45 names with certainty.

### Resolved IPC callback names from their own machine-code references

The previously unnamed 45 direct-DP-write callback groups can now be associated with source-level **`IHmiKss` callback names** using each function's own PC-relative reference to the literal diagnostic `<method>(): batchLock() failed`. This avoids guessing names by proximity or callback order.

**Verified against the original ELF:** **33 of 45** direct-write groups have an unambiguous diagnostic-derived name; **12 remain unidentified** because their function bodies do not reference that diagnostic form. This is stronger than string inventory alone: it associates the *specific ARM callback address* with the *named method* and with its exact DP writes.

| Function address | `IHmiKss` callback | Direct DP writes |
| --- | --- | ---: |
| `0x694728` | `BMS_10` | 1 |
| `0x694850` | `TelltaleAALA_Display` | 6 |
| `0x69495c` | `Systeminfo01` | 2 |
| `0x6949f0` | `ActTest_SoftLEDs` | 8 |
| `0x694b14` | `ActTest_CommonSoftLEDs` | 9 |
| `0x694c50` | `HVK_01` | 2 |
| `0x694d90` | `TelltaleHMI_Blink` | 7 |
| `0x694e9c` | `NVEM_02` | 2 |
| `0x694f30` | `KombiDef` | 8 |
| `0x695054` | `FanControl` | 2 |
| `0x6950e8` | `Config_Antrieb` | 2 |
| `0x69517c` | `DS_VCM_DisplayArea` | 3 |
| `0x69526c` | `Gear_Display02` | 5 |
| `0x695348` | `Gear_Display` | 12 |
| `0x6954cc` | `Motor_Hybrid_06` | 3 |
| `0x6955c0` | `ACC_HMI_Display` | 4 |
| `0x695724` | `CarOutline_HMI` | 9 |
| `0x6958d4` | `ACC_02` | 3 |
| `0x6959b8` | `ACC_12` | 2 |
| `0x695a60` | `VZE_01` | 4 |
| `0x695bc4` | `HMI_C_NightVision_Display` | 6 |
| `0x695cf4` | `Config_Driverassist_Media` | 14 |
| `0x695ee8` | `TelltaleHMI_Display` | 10 |
| `0x696140` | `ZPM_HMI_Info` | 2 |
| `0x696264` | `Config_Coding` | 13 |
| `0x6965f4` | `Config_View_Specifica` | 8 |
| `0x69676c` | `HMI_EngineID_MKB` | 1 |
| `0x696a90` | `HMI_Motor_26` | 2 |
| `0x696cfc` | `Config_Installation_Coding` | 4 |
| `0x696fc0` | `TSK_07` | 4 |
| `0x6970d8` | `ODO_HMI_Distance` | 2 |
| `0x697264` | `TCH_HMI_EngineRPM` | 2 |
| `0x6976d8` | `ECT_HMI_Information` | 2 |

The 12 currently unidentified direct-write groups start at `0x6942f0`, `0x694448`, `0x695898`, `0x696540`, `0x6965a8`, `0x696958`, `0x6969e8`, `0x696a20`, `0x696a58`, `0x696b6c`, `0x696c00`, `0x696f4c`. Some can be tiny helper routines or alternate callback implementations; **do not label them by adjacent method** without a callgraph or vtable reference.

The new `name_rte_dp_callbacks.py` tool reproduces the **callback name → function address → DP ID → payload offset/width** mapping directly from ELF bytes:

```sh
python3 tools/fpk1/research/gtf2/name_rte_dp_callbacks.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-ipc-named-dp-fields.csv
```

This closes the callback-name attribution gap for **33 groups**, but not the ASI method-number/serialization gap. The latter requires vtable/registration analysis or runtime IPC traces.

### Downstream cross-references: IPC-written DP IDs into GTF2 HMI code

The next analysis follows all **176 unique DP IDs** written by the direct RTE callbacks, not just their input payload mapping. For each DP ID it locates matching 32-bit constants in the original ELF and verifies a **real ARM PC-relative LDR instruction** targeting that constant. It excludes the callback-writer instruction range `0x694000–0x697fff`.

Local execution on the original ELF found **813 non-writer instruction references**:

| Code region (heuristic only) | References |
| --- | ---: |
| `0x550000–0x62ffff` — view/HMI implementation region | **575** |
| `0x210000–0x22ffff` — initialization/configuration region | **142** |
| Other GTF2 code | **96** |
| **Total** | **813** |

The references are real instruction→literal edges, but **not necessarily DP value reads**: a use may register a callback, initialize a descriptor, compare an event's DP ID, or retrieve a value. Classifying those operations requires instruction-by-instruction tracing.

Specific downstream reference points:

| IPC source | DP ID | Non-writer ARM instruction references |
| --- | --- | --- |
| `TCH_HMI_EngineRPM` | `0x02000293` | `0x59ee80`, `0x59f370`, `0x5c9310` |
| `TCH_HMI_EngineRPM` | `0x02000295` | `0x5753bc`, `0x59ee1c`, `0x59f2e0`, `0x5c6000` |
| `Gear_Display` | `0x020001f7` | `0x569150` |
| `Gear_Display` | `0x020001f9` | `0x219ba8`, `0x5fdbf8`, `0x5fdcb4`, `0x5fdd74` |

**Concrete consumer behavior:** at `0x5fdbf4–0x5fdc20`, GTF2 reads an incoming record's **`+0x04` DP identifier**, compares it against literal **`0x020001f9`** loaded at `0x5fdbf8`, returns `1` for non-matches, and tail-branches to **`0x5fdb8c`** for matches. This is an actual **DP-ID-specific event filter/dispatch** for a `Gear_Display` field, not proof of a direct rendering call. Other references must be classified separately.

Reproduce and export all links (no firmware bytes in repository):

```sh
python3 tools/fpk1/research/gtf2/trace_rte_dp_consumers.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/trace_rte_dp_consumers.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-ipc-dp-consumers.csv
```

The next necessary step is to distinguish **DP subscription/registration** from **DP event handling and DP value reads** at these references, then link event filters to the specific view object or coordinator function. The count **575** must not be presented as 575 screen changes or as a list of rendered fields.

### Gear_Display DP 0x020001f9: actual downstream state reaction

The previously found event filter at `0x5fdbd8–0x5fdc20` is now followed through its **actual target**, `0x5fdb8c`. The original ARM ELF bytes establish this control flow:

```text
0x5fdc28: check incoming event kind == 2
  -> 0x5fdbd8:
       call 0x122498 to normalize/obtain the event record
       read record+0x04 DP ID
       compare against 0x020001f9
       non-match -> return 1
       match -> tail branch to 0x5fdb8c
  -> 0x5fdb8c:
       query GTF2 state via 0x219b78 (which reads DP through 0x69ec38)
       invoke virtual slot +0x70 on the receiver object
       call 0x6528f0(receiver, state != 0 ? 1 : 0)
       return 1
  -> 0x6528f0:
       if receiver+0x1b8 bit0 set and receiver+0xfc is non-null:
           call 0x63669c, then notify via 0x14cb48
           set receiver+0xe3 bit4
       otherwise:
           update receiver+0xf8 with new boolean state
           if changed, set receiver+0xe3 bit4
```

This **proves a concrete UI-object state reaction** to an IPC-fed `Gear_Display` field: the object is notified or has its cached boolean state updated and is marked dirty when the value changes. The exact semantic label of that boolean and the visible pixels affected remain unproven; **do not call it a gear-label repaint without additional evidence**. The branch on receiver+0x1b8 shows two distinct update modes.

Machine-code evidence:

| VA | Meaning |
| --- | --- |
| `0x5fdc24` | literal `0x020001f9` |
| `0x5fdbf4–0x5fdbfc` | load incoming record+4 and compare DP ID |
| `0x5fdc20` | tail branch to `0x5fdb8c` |
| `0x5fdb98` | direct BL to state query `0x219b78` |
| `0x5fdba8` / `0x5fdbbc` | load receiver virtual slot `+0x70` |
| `0x5fdbcc` | direct BL to state helper `0x6528f0` |
| `0x6528f4` | test receiver+0x1b8 |
| `0x65294c–0x652960` | cached-state update at receiver+0xf8 and dirty bit4 at +0xe3 |
| `0x652938` | notification call `0x14cb48` |

The exact branch and call words are checked by the committed verifier:

```sh
python3 tools/fpk1/research/gtf2/verify_gear_dp_reaction.py /path/to/gtf2
```

The six direct BL targets and twelve ARM instruction words were independently checked against the extracted original ELF. This is a stronger result than counting DP-ID xrefs: it establishes **a specific callback and state-change consequence** while preserving the distinction between state updates and rendering.

### Gear_Display DP event adapters: object owner and three registrations

The DP `0x020001f9` handler can now be tied to a **specific GTF2-owned embedded object**, rather than only an anonymous callback. The global/owner object uses a fixed embedded offset **`+0x56e2c`**; during its construction, the instruction at **`0x267064`** calls constructor **`0x5ee2b0`** with `owner+0x56e2c`. The constructor invokes base constructor `0x6ade90` and installs vtable **`0x87f808`** into the embedded object's first word.

The vtable `0x87f808` contains:

| Slot | Function | Observed purpose |
| --- | --- | --- |
| `+0x00` | `0x5ed688` | destructor/base thunk (branches to `0x6adea0`) |
| `+0x04` | `0x5fdc40` | direct dispatch into `0x5fdb8c` |
| `+0x08` | `0x5fdc28` | checks event kind 2 and filters DP ID `0x020001f9` |

Two **additional vtables** have event-filter functions for the **same DP ID**, but are separate objects/adapters, not three different DP signals:

| Vtable | Direct dispatch | Kind-2 event filter | DP-ID literal |
| --- | --- | --- | --- |
| `0x87f808` | `0x5fdc40` | `0x5fdc28` | `0x5fdc24` |
| `0x87fb38` | `0x5fdcfc` | `0x5fdce4` | `0x5fdce0` |
| `0x87f910` | `0x5fddbc` | `0x5fdda4` | `0x5fdda0` |

The state query **`0x219b78`** also reads exactly **DP `0x020001f9`** via the data-pool accessor **`0x69ec38`** (call at `0x219bac`). It combines this with three GTF2-owned queries `0x2183cc`, `0x218478`, `0x21839c`; their return values control whether the signed 16-bit DP result is used. Thus the event handler does **not** blindly copy the incoming byte to a display property: it computes a derived boolean/availability state and then calls the receiver's virtual `+0x70` and the state-change helper `0x6528f0`.

Reproduce the exact embedded-object offset, three vtable triples and three identical DP literals:

```sh
python3 tools/fpk1/research/gtf2/verify_gear_dp_owner.py /path/to/gtf2
```

**Unresolved:** the semantic class name for the embedded adapter and the rendered property on the Kanzi scene graph. The vtable/owner linkage is certain; a gear glyph, warning icon or specific screen cannot yet be assigned solely from these instructions. The distinction between **adapter object** and **final visual receiver** is important: the callback passes a receiver pointer as an argument, so the adapter's vtable does not identify that receiver's concrete type.

### Gear DP 0x020001f9: exact state gate and receiver update truth table

Instruction-level follow-up to the adapter/owner analysis establishes **why some Gear_Display updates do not change the UI**:

- At `0x219b78`, GTF2 executes three prerequisite checks (`0x2183cc`, `0x218478`, `0x21839c`), then reads the **signed 16-bit** value for `0x020001f9` via `0x69ec38` into stack `sp+6`.
- The result is **zero** when **all three prerequisite checks return zero**, irrespective of the DP value. Otherwise, the result is **one iff the signed 16-bit DP value is nonzero**. This means the UI-facing state is gated by three other GTF2-owned conditions; their business semantics remain to be recovered.
- `0x5fdb8c` uses that boolean, invokes the receiver virtual method at `vtable+0x70`, and calls `0x6528f0` with the boolean as the second argument.
- `0x6528f0` has **three**, not two, distinct outcomes:

| Receiver state | Observable code effect |
| --- | --- |
| `receiver[0x1b8] & 1 == 0` | Write boolean to `receiver[0xf8]`; set dirty bit `0x10` in `receiver[0xe3]` **only if old and new differ** |
| `receiver[0x1b8] & 1 != 0` and `receiver+0xfc != NULL` | Call `0x63669c`, notify via `0x14cb48`, and set dirty bit `0x10` |
| `receiver[0x1b8] & 1 != 0` and `receiver+0xfc == NULL` | **Return without updating the cached byte or dirty bit** |

The third case corrects an oversimplification in the earlier description of the state helper: **a missing external receiver in active mode suppresses the update**. Also, `0x219b78` does not simply forward the IPC payload; it applies three gating conditions.

The committed verifier checks **24 exact ARM words** for these branch conditions, DP read, virtual slot and notification behavior:

```sh
python3 tools/fpk1/research/gtf2/verify_gear_dp_state_gates.py /path/to/gtf2
```

This establishes precise **state-change/no-change conditions** for the DP-driven event. The final receiver's concrete class, the meaning of the three gates and the actual Kanzi property remain unproven; a pixel-level interpretation still needs further evidence.

### Exact meaning of the three Gear_Display state gates: one selector DP

Further disassembly resolves the previously opaque prerequisite functions. They are **three predicates over the same DP `0x06400dc6`**, not three independent boolean state variables:

| Predicate VA | DP ID read by `0x69ec38` | Signed 16-bit values returning true |
| --- | --- | --- |
| `0x2183cc` | `0x06400dc6` (literal at `0x2183f8`) | **5, 10** |
| `0x218478` | `0x06400dc6` (literal at `0x2184a4`) | **9, 15** |
| `0x21839c` | `0x06400dc6` (literal at `0x2183c8`) | **2, 14** |

At `0x219b78` the three predicates are called at `0x219b80`, `0x219b8c`, `0x219b98`; the same function then reads Gear_Display DP `0x020001f9` at `0x219bac`. The resulting boolean is exactly:

```text
gear_dp_state =
    (selector_dp_0x06400dc6 in {2,5,9,10,14,15})
    AND (signed16(DP_0x020001f9) != 0)
```

Both inputs are obtained through the GTF2 DP accessor `0x69ec38`, not directly from the IPC payload at this stage. The six selector values are confirmed from literal `CMP` instructions. The **human-readable meaning** of selector DP `0x06400dc6` (possibly a mode or configuration enum) is still unknown; do not assign semantic names to values 2/5/9/10/14/15 without further proof.

This also establishes that the gate is **not three independent input signals**. The same selector DP is referenced by many other GTF2 routines, including `0x217bb0`, `0x218350`, `0x21837c`, `0x218408`, `0x218434`, and `0x218484`, which compare it against additional enum values. These references suggest a shared multi-valued application selector, but do not identify its label.

The exact bytes and direct BL edges have been verified against the original extracted GTF2 ELF. Reproduce:

```sh
python3 tools/fpk1/research/gtf2/verify_gear_selector_dp.py /path/to/gtf2
```

**Consequence:** a nonzero incoming Gear_Display field does not trigger this receiver's true state outside those six selector values, and even inside the allowed set the receiver's active/no-target branch can suppress a state update (see preceding section).

### Additional IPC events: engine RPM and a second Gear_Display field

To avoid overfocusing on `Gear_Display` DP `0x020001f9`, the HMI event dispatchers have now been traced for **two other DP IDs** written by `IHmiKss` callbacks.

**Engine RPM (`TCH_HMI_EngineRPM`, incoming `payload+0x02`, DP `0x02000295`):**

```text
0x6972a4: callback writes DP 0x02000295
  -> HMI event dispatcher:
     0x5753bc: load literal 0x02000295 from 0x575130
     0x5753c0: compare event DP ID in r8
     0x5753c4: on equality branch to 0x5863d0
  -> 0x5863d0:
     load first object pointer from owner-relative slot
     object1[0xe3] |= 0x10
     load second object pointer from another owner-relative slot
     object2[0xe3] |= 0x02
     branch to common dispatcher continuation 0x597c7c
```

This is a **direct two-object dirty-flag reaction** to a particular engine-RPM DP change. It does not require a `Gear_Display` selector gate and does not prove immediate rendering. The two owner-relative slot constants are at `0x58554c` and `0x585550`; identifying the object classes requires following their initialization.

**Gear_Display, another field (`payload+0x00`, DP `0x020001f7`):**

```text
0x695374: callback writes DP 0x020001f7
  -> HMI event dispatcher:
     0x569150: load literal 0x020001f7 from 0x569ccc
     0x569154: compare event DP ID in r4
     0x569158: on equality branch to 0x56d2b4
  -> 0x56d2b4:
     obtain GTF2 object via 0x2bae28
     invoke virtual method at vtable+0x08 with argument 31
     call 0x5600d8 to obtain another receiver
     invoke its virtual method at vtable+0x70
     update receiver flags and return to dispatcher
```

Thus **two fields of the same incoming `Gear_Display` record trigger different HMI mechanisms**: `0x020001f9` follows the gated boolean-state adapter, while `0x020001f7` invokes object virtual methods. The semantic meaning of argument `31` and the receiver classes remain unresolved; do not infer a particular gear symbol or screen.

The original ELF was checked locally with **21 exact ARM instruction words and both conditional branch targets**, using:

```sh
python3 tools/fpk1/research/gtf2/verify_other_ipc_events.py /path/to/gtf2
```

**Classification caution:** references in `0x2a0xxx` and `0x59exxx` for other DP IDs are often bulk descriptor initialization (`LDR literal` followed by `STR`), not event consumers. The two paths above are established by **literal comparison → conditional branch → receiver-side effects**, a higher evidence standard than a mere xref.

### Additional IHmiKss event reactions: ACC, odometer and telltales

Three further IPC-fed DP IDs were matched to the **actual HMI event dispatcher** via `LDR literal → CMP event ID → BEQ target` and then traced into receiver code. All three are distinct from the previously traced RPM and Gear_Display paths.

| Incoming callback | Payload-to-DP write | Dispatcher comparison | Matching event target | Verified side effect |
| --- | --- | --- | --- | --- |
| `ACC_HMI_Display` | `0x6955f4` → `0x02000297` | `0x57535c–0x575364` (literal `0x575128`) | `0x58644c` | Load receiver from owner-relative slot `0x58555c`, resolve via `0x6218cc`, then call its vtable slot `+0x00` with event arguments; return to common dispatcher `0x597c7c` |
| `ODO_HMI_Distance` | `0x69710c` → `0x020002c2` | `0x575498–0x5754a0` (literal `0x575144`) | `0x58696c` | Set bit `0x08` in byte `+0x06` of **two** owner-held objects; resolve a **third** receiver via `0x6218cc` and invoke its virtual event method |
| `TelltaleHMI_Display` | `0x695fbc` → `0x0200021d` | `0x574dcc–0x574dd4` (literal `0x5750f0`) | `0x583ff0` | Resolve receiver via `0x6218cc`, then invoke its virtual event method, passing event kind `2` |

The odometer's first two object slots are read using offsets **`0x4a54c`** and **`0x50834`** (literals `0x5873dc`, `0x5873e0`), and the third via **`0x4a8e4`** (`0x5873e4`). The first two flags are set at `0x586980–0x586988` and `0x586998–0x5869a0`. These are **not** the same `+0xe3` dirty bits used in the RPM example; the role of `+0x06` needs class-specific interpretation.

The ACC and telltale paths use a receiver's **virtual slot `+0x00`** after `0x6218cc`. That is the observed event forwarding operation; its concrete implementation and on-screen effect require vtable resolution. Neither path alone proves a visible ACC icon or telltale lamp changed.

The committed verifier checks **29 exact ARM instruction/literal words** and **three conditional branch targets** against the original extracted GTF2 ELF:

```sh
python3 tools/fpk1/research/gtf2/verify_acc_odo_telltale_events.py /path/to/gtf2
```

This brings the independently traced **IPC→DP→HMI event routes to six**: Gear_Display `0x020001f9`, Gear_Display `0x020001f7`, RPM `0x02000295`, ACC `0x02000297`, odometer `0x020002c2`, and telltale `0x0200021d`. These six routes are **examples**, not exhaustive coverage of the 176 DP writes. All three newly added routes are statically verified; no runtime rendering observation is claimed.

### Expanded HMI event dispatch coverage: 24 direct RTE DP routes

An additional **24 instruction-verified conditional event dispatch edges** have been recovered by scanning the original GTF2 ARM code at `0x570000–0x57ffff`. Each edge requires three linked facts: a PC-relative literal **equal to a DP ID actually written by an RTE callback**, a following `CMP` against the event ID, and an **equal-conditional branch** to a concrete HMI handler address. The scanner does not mistake DP descriptor initialization for a dispatched event.

| Incoming DP ID | Incoming RTE writer call | HMI CMP | Matching handler |
| --- | --- | --- | --- |
| `0x02000225` | `0x6967a0` | `0x574020` | `0x584710` |
| `0x0200010b` | `0x6966b4` | `0x5747c8` | `0x5796f0` |
| `0x02000178` | `0x6948fc` | `0x57492c` | `0x57d410` |
| `0x02000175` | `0x6965c0` | `0x5749dc` | `0x57d280` |
| `0x020001ef` | `0x69541c` | `0x574ac8` | `0x5816ec` |
| `0x020001c2` | `0x695e58` | `0x574b30` | `0x58014c` |
| `0x020001e6` | `0x694b5c` | `0x574bbc` | `0x5812a8` |
| `0x020001ea` | `0x694a9c` | `0x574c30` | `0x5813ec` |
| `0x020001ec` | `0x695430` | `0x574c54` | `0x581530` |
| `0x020001f6` | `0x6953b8` | `0x574cd0` | `0x581a64` |
| `0x020001fd` | `0x6953f4` | `0x574cfc` | `0x582020` |
| `0x02000200` | `0x694b84` | `0x574d20` | `0x582200` |
| `0x02000201` | `0x694b70` | `0x574d40` | `0x582240` |
| `0x02000216` | `0x694dc4` | `0x574da4` | `0x582ee0` |
| `0x0200021d` | `0x695fbc` | `0x574dd0` | `0x583ff0` |
| `0x0200021f` | `0x694e3c` | `0x574df4` | `0x5843d4` |
| `0x02000230` | `0x695514` | `0x574ea0` | `0x58490c` |
| `0x02000297` | `0x6955f4` | `0x575360` | `0x58644c` |
| `0x02000295` | `0x6972ac` | `0x5753c0` | `0x5863d0` |
| `0x020002ad` | `0x6957a8` | `0x57542c` | `0x586738` |
| `0x020002c2` | `0x69710c` | `0x57549c` | `0x58696c` |
| `0x020002cd` | `0x695f6c` | `0x5754bc` | `0x586bf0` |
| `0x020002d2` | `0x695f94` | `0x5754ec` | `0x586cd0` |
| `0x020002d3` | `0x695fd0` | `0x57550c` | `0x586d34` |

This table **includes** previously documented RPM, ACC, odometer and telltale routes; it does not mean 24 new routes on top of those examples. The previously documented `Gear_Display` DP `0x020001f7` comparison is in a separate HMI dispatcher code range (`0x569xxx`), so is not counted here. Likewise `0x020001f9` uses a dedicated event adapter at `0x5fdxxx`.

Three newly examined handler bodies demonstrate **different consequences**:

- **`0x020001ef` (`Gear_Display`, payload byte `+0x0a`) → `0x5816ec`:** invokes owner virtual `+0x08` with selector values **31, 32, 36** on successive paths; invokes receiver virtual `+0x70`; sets bit **`0x04` in receiver byte `+0xe4`**. This is a multi-object update, distinct from the gated boolean DP `0x020001f9`.
- **`0x020002ad` (`CarOutline_HMI`, payload byte `+0x05`) → `0x586738`:** obtains an owner-held object via `0x2bae28`, then sets **bit `0x10` in object byte `+0xe6`**, and returns to the shared event dispatcher `0x597c7c`. The next code path at `0x586754` sets bit `0x20` in that same byte for a separate event. Do not infer a specific car-outline graphic without resolving the object.
- **`0x02000225` (`HMI_EngineID_MKB`, payload byte `+0x0c`) → `0x584710`:** obtains an object through `0x6218cc` and forwards an event with kind **2** to a virtual receiver. It then proceeds to another receiver. The exact visible effect remains unknown.

**Reproduction:**

```sh
python3 tools/fpk1/research/gtf2/scan_rte_hmi_dispatch.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-rte-hmi-dispatch.csv
```

The **24** count is for the strict `0x57xxxx` dispatcher scan only; not all 176 DP writes are expected to have this exact code shape. A matching event target is not equivalent to a pixel change. Follow-up should classify each handler by whether it writes object flags, calls a virtual receiver, changes a view selection, or performs only a guard check.

### Further classification: single-object dirty bit versus two-receiver event fan-out

The previously identified 24 RTE-fed HMI dispatch edges are **not uniform**. Two additional handlers have been examined at instruction level, illustrating two distinct behaviors:

| DP ID / incoming callback | Dispatcher match | Handler | Verified behavior |
| --- | --- | --- | --- |
| `0x02000230` — `Motor_Hybrid_06` (direct writer at `0x695514`) | `0x574ea0` → BEQ `0x574ea4` | `0x58490c` | Load owner-held object at offset **`0x2e7b4`** and set **`object[0xe3] |= 0x01`**, then branch to `0x597c7c` |
| `0x020002d2` — `TelltaleHMI_Display` (direct writer at `0x695f94`) | `0x5754ec` → BEQ `0x5754f0` | `0x586cd0` | Resolve **two distinct receivers** via `0x6218cc`, invoke each receiver's virtual slot `+0x00` with event kind **2**, then branch to `0x597c7c` |

**Exact `0x02000230` effect** at `0x58490c–0x584920`: `LDR` object pointer from owner `+0x2e7b4`, `LDRB` from `object+0xe3`, `ORR #1`, `STRB` to `object+0xe3`, unconditional return to common dispatch. No virtual receiver call occurs in this handler. The preceding/following dispatch handlers can set other bits in the same byte, but those must not be attributed to this event.

**Exact `0x020002d2` effect** at `0x586cd0–0x586d30`: first receiver resolved at `0x586ce0` and invoked at `0x586d00`; second resolved at `0x586d0c` and invoked at `0x586d2c`. Both invocations use `r3=2`, i.e. HMI event kind 2. The handler itself does **not** directly set a dirty bit. Whether either receiver ultimately changes an icon depends on its concrete vtable implementation.

These paths are useful for classification of the other dispatcher targets: a **direct flag write** and **virtual event fan-out** are different operations, even though both are triggered by an incoming RTE DP update. This does not yet establish a screen/view switch for either case.

Reproduce with the exact ARM-word verifier:

```sh
python3 tools/fpk1/research/gtf2/verify_hmi_dirty_vs_fanout.py /path/to/gtf2
```

The verifier checks **23** literal/instruction words including both event branch sites, the object offset, the bytewise flag update, and both virtual event calls.

### Two more verified multi-receiver HMI event fan-outs

A follow-up to the 24-route dispatch table confirms **two more** events that fan out to two distinct receiver objects. These are already present in the dispatch inventory; this section adds **receiver-level effects**, not two new unique DP IDs.

| Incoming DP | Comparison / BEQ | Handler | First receiver owner slot | Second receiver owner slot |
| --- | --- | --- | --- | --- |
| `0x02000225` (`HMI_EngineID_MKB`) | `0x574020 / 0x574024` | `0x584710` | `+0x4b02c` (literal `0x583928`) | `+0x51310` (literal `0x58392c`) |
| `0x020001e6` (writer at `0x694b5c`) | `0x574bbc / 0x574bc0` | `0x5812a8` | `+0x1f5d0` (literal `0x581b84`) | `+0x1fb00` (literal `0x581b88`) |

Both routes obtain receiver objects via `0x6218cc`, load the receiver vtable and invoke its **first virtual method** with event kind `2`. For `0x02000225`, the two indirect calls are at `0x584750` and `0x584794` (register `r11`); for `0x020001e6`, at `0x5812d8` and `0x581304` (register `r12`). The caller also constructs separate event/context pointers for each receiver, rather than forwarding a single object pointer unchanged.

The static analysis has been reproduced against the original **SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`** GTF2 binary:

```sh
python3 tools/fpk1/research/gtf2/verify_rte_event_fanout.py /path/to/gtf2
```

This verifier checks both event DP literals, both `CMP`/conditional branch edges, **four receiver slot literals**, **four indirect calls**, and the **four event-kind assignments**. The two concrete receiver classes and visual elements are still unknown. Importantly, a fan-out is not a screen transition; it only proves multiple object-level event deliveries.

### Cross-event convergence: two different DP IDs, the same HMI receivers

Comparing the already identified fan-out handlers revealed a **shared pair of receiver wrappers**. This is stronger evidence than merely seeing the same virtual call sequence.

| Incoming DP | Handler | Wrapper 1 owner offset | Wrapper 2 owner offset | Context 1 offset | Context 2 offset |
| --- | --- | --- | --- | --- | --- |
| `0x020001e6` | `0x5812a8` | `0x1f5d0` | `0x1fb00` | `0x1f5cc` | `0x1fafc` |
| `0x020002d2` | `0x586cd0` | `0x1f5d0` | `0x1fb00` | `0x1f5cc` | `0x1fafc` |

**Proof from original ARM code:**

- `0x581b84` and `0x587410` contain the same first wrapper offset `0x1f5d0`; `0x581b88` and `0x587540` contain the same second wrapper offset `0x1fb00`.
- Both handlers construct context pointers using `ADD owner,#0x1f400; ADD #0x1cc` and `ADD owner,#0x1f800; ADD #0x2fc`, respectively, yielding `owner+0x1f5cc` and `owner+0x1fafc`. **Each context is four bytes before its wrapper**, in both handlers.
- The function previously described as a generic receiver resolver, `0x6218cc`, is actually just `LDR r0,[r0,#0xb8]; BX lr`: it dereferences the wrapper's **`+0xb8` target pointer**. Thus each handler's call sequence is `wrapper=owner[slot]` → `receiver=wrapper[0xb8]` → `receiver->vtable[0](receiver,context,event,kind=2,...)`.
- Four indirect `BLX r12` calls (`0x5812d8`, `0x581304`, `0x586d00`, `0x586d2c`) and four `MOV r3,#2` sites prove both events are forwarded to **both** receivers with event kind `2`.

**Interpretation:** distinct DP updates converge onto the same two receiver objects and matching per-receiver contexts. This indicates shared HMI object-level handling, **not** necessarily identical rendered output: the incoming event ID and arguments can still differ. The concrete vtable implementations and visible properties remain to be recovered.

A new verifier checks **22 exact ARM words** (including literals, context arithmetic, pointer accessor, event kinds and indirect calls) against the original ELF. It was executed successfully on the local binary:

```sh
python3 tools/fpk1/research/gtf2/verify_shared_hmi_receivers.py /path/to/gtf2
```

### Event purpose must be separated into source semantics, state mutation, and rendering

The key research question is **what each event means**, not just which handler it reaches. An event can update a DP, cause a model/object dirty flag, and let the declarative HMI scene react later. A dirty bit or virtual event call **does not prove immediate drawing**. A precise mapping must distinguish:

1. **Source contract (confirmed):** `IHmiKss` callback name, payload field offset/width, DP ID. Callback names are taken from GTF2's **own diagnostic strings**, not guessed from addresses.
2. **HMI reaction (confirmed when traced):** dispatcher comparison, handler, receiver objects, flags, virtual calls, value predicates.
3. **Screen meaning (open until proven):** the specific warning lamp, gauge, icon, text, view/scene and visible result. This requires receiver class/property bindings, view data, scene resources or runtime evidence.

A reproducible catalog now maps all **24** directly dispatched RTE-fed DP fields in the `0x57xxxx` dispatcher to their **actual source callbacks**; **23/24** have a diagnostic-string-confirmed callback name, one remains unidentified.

| Source callback | DP ID → payload field offset (width) | Source-level meaning / limitation |
| --- | --- | --- |
| `HMI_EngineID_MKB` | `0x02000225` → `+0x0c` (u8) | Engine identification/configuration input; precise enum unknown |
| `Config_View_Specifica` | `0x0200010b` → `+0x0a` (u8) | View-specific configuration; exact view/bit unknown |
| `TelltaleAALA_Display` | `0x02000178` → `+0x09` (u8) | AALA telltale display field; exact lamp unknown |
| **unidentified** | `0x02000175` → `+0x02` (u8) | Source callback not identified; do not label |
| `Gear_Display` | `0x020001ef` → `+0x0a`; `0x020001ec` → `+0x09`; `0x020001f6` → `+0x03`; `0x020001fd` → `+0x06` (all u8) | Four distinct gear-related fields; do **not** conflate with already studied `0x020001f7` and `0x020001f9` |
| `Config_Driverassist_Media` | `0x020001c2` → `+0x0f` (u8) | Driver-assist/media configuration; precise option unknown |
| `ActTest_CommonSoftLEDs` | `0x020001e6` → `+0x01`; `0x02000200` → `+0x03`; `0x02000201` → `+0x02` (all u8) | **Actuator test** of common software indicators; individual LED identity unknown |
| `ActTest_SoftLEDs` | `0x020001ea` → `+0x06` (u8) | Actuator test of software indicators; individual LED identity unknown |
| `TelltaleHMI_Blink` | `0x02000216` → `+0x02`; `0x0200021f` → `+0x01` (u8) | **Blink control** fields, distinct from steady display |
| `TelltaleHMI_Display` | `0x0200021d` → `+0x08`; `0x020002cd` → `+0x04`; `0x020002d2` → `+0x06`; `0x020002d3` → `+0x0b` (u8) | **Display state** fields for telltales; which lamp and value meanings unknown |
| `Motor_Hybrid_06` | `0x02000230` → `+0x04` (u16) | Hybrid powertrain input; exact quantity/units unknown |
| `ACC_HMI_Display` | `0x02000297` → `+0x08` (u16) | ACC display input; precise display property unknown |
| `TCH_HMI_EngineRPM` | `0x02000295` → `+0x02` (u16) | Engine RPM-related input; scale/units not established from callback name alone |
| `CarOutline_HMI` | `0x020002ad` → `+0x05` (u8) | Vehicle-outline display input; exact door/zone/icon unknown |
| `ODO_HMI_Distance` | `0x020002c2` → `+0x08` (u8) | Odometer/distance-related field; **not necessarily the complete odometer value** |

**New cross-event insight:** `ActTest_CommonSoftLEDs` field `+0x01` (DP `0x020001e6`) and `TelltaleHMI_Display` field `+0x06` (DP `0x020002d2`) reach **the same pair of receiver wrappers** (owner offsets `0x1f5d0` and `0x1fb00`). A reasonable **hypothesis** is that ordinary telltale display and software-indicator actuator testing converge on shared UI elements. This is **not yet proof** of which individual lamps or that the two values have the same interpretation. A shared receiver can distinguish events by ID or context.

**Reproduce the source-semantic inventory:**

```sh
python3 tools/fpk1/research/gtf2/catalog_rte_event_semantics.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-event-semantics.csv
```

**Research priority:** trace the two shared receivers' `wrapper+0xb8` targets and concrete vtables, and search their property/scene bindings. Separately, recover the per-field value-to-enum/bit meaning from GTF2 consumers or firmware schema; **never equate a callback name with an exact display effect**. The table is limited to 24 strictly verified `0x57xxxx` dispatch edges; other RTE DP writes, including non-direct and separate-dispatch paths, remain to be cataloged.

### Scene-level semantics: evidence-gated event matrix

**Working hypothesis (not yet proven):** an RTE/IPC callback changes a DP or object property; the scene graph then reacts through a binding, observer, or dirty-flag processing. Direct object flags such as `+0xe3`, `+0xe4`, `+0xe6`, and `+0x06` are **not themselves proof of a particular visual effect**. Likewise a virtual event call is not automatically a scene transition.

A new script, `tools/fpk1/research/gtf2/build_scene_event_matrix.py`, creates a **24-row evidence-gated catalog**. It checks each event's DP literal and conditional branch target in the supplied GTF2 ELF, and records these separate columns:

- `dp_id`, `callback`, `payload_offset`, `family`, `handler_va`, `dispatch_proof`: **confirmed static facts**;
- `property_id`, `scene_node`, `binding`, `visual_effect`: explicitly **unresolved**, pending scene asset / object metadata / vtable proof;
- `scene_switch`: **not_proven** rather than assuming a scene change.

The 24 dispatches contain **23 named callback provenances** and one still unidentified callback. Their coarse **functional families** are based only on callback names; do not interpret these as exact per-byte semantics. For example, `Config_View_Specifica` identifies a configuration-related callback, **not** proof that payload `+0x0a` switches a view. `TelltaleHMI_Blink` names a blink-related callback, **not** proof of which lamp or which animation is activated by payload `+0x02`.

Notable families and current constraints:

| Callback family | Examples of exact DP IDs | What is proven | Scene-level question still open |
| --- | --- | --- | --- |
| View/driver-assist configuration | `0x0200010b`, `0x020001c2` | IPC field written and matching HMI handler entered | Does it select a view, configure a property, or enable a scene feature? |
| Gear data | `0x020001ef`, `0x020001ec`, `0x020001f6`, `0x020001fd` | Four different DP fields each have an event handler | Which field selects gear text/icon versus visibility or animation? |
| Telltales and blink | `0x02000178`, `0x02000216`, `0x0200021d`, `0x0200021f`, `0x020002cd`, `0x020002d2`, `0x020002d3` | Multiple indicator event routes; one (`0x020002d2`) fans out to two receivers | Which lamp and blink property corresponds to each field? |
| Indicator test | `0x020001e6`, `0x020001ea`, `0x02000200`, `0x02000201` | Test callbacks reach HMI; `0x020001e6` shares two receivers with `0x020002d2` | Are these shared indicator nodes in test/normal modes? |
| Vehicle status | `0x02000295`, `0x02000297`, `0x020002c2`, `0x020002ad`, `0x02000230` | Engine RPM, ACC, odometer, car outline, hybrid callbacks and concrete HMI dispatches | Which scene properties consume the values? |

This distinguishes **event purpose at callback level** from **specific field meaning**, **property mutation**, and **visual scene reaction**. Do not claim full semantic resolution of the 24 events.

Reproduce:

```sh
mkdir -p build_fpk1/research-artifacts
python3 tools/fpk1/research/gtf2/build_scene_event_matrix.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-scene-event-matrix.csv
```

**Next evidence threshold:** resolve the receiver wrapper `+0xb8` assignment and receiver vtables; identify property identifiers / scene node names in the GTF2-owned scene resources; match a specific DP-driven mutation to a scene binding or observer. Only then populate `property_id`, `scene_node`, `binding`, or `visual_effect` with concrete names.

### Scene assets and node/property metadata: first concrete evidence from GTF2 ELF

The extracted GTF2 binary itself contains **scene-resource filenames, node paths, and property metadata keys**. These are more useful for the scene question than classifying event dispatches alone. Examples with exact string virtual addresses:

| Class | Exact literal in GTF2 | VA |
| --- | --- | --- |
| Scene resource | `AU736_CarOutline.kzb` | within the `0x7c30xx` resource filename block |
| Scene resource | `AU736_Tubes.kzb` | within the `0x7c30xx` resource filename block |
| Scene resource | `DisplaySupervisor.kzb` | present in ELF string data |
| Node path | `MV_ClusterFull.TubeContainer.CenterTube.GearIndicator` | present in ELF string data |
| Node path | `MV_ClusterFull.TubeContainer.RevoTube.GearIndicatorPHEV` | present in ELF string data |
| Node path | `PV_WarnPopup_CarOutline.GlassPlate.CarOutline` | present in ELF string data |
| Node path | `RV_ClusterFull_Additional.HubContentRevoTube.CarOutline` | present in ELF string data |
| Property metadata key | `CRUISE_active_bool_propertyName` | `0x7fa8ec` |
| Property metadata key | `AALA_active_bool_propertyName` | `0x7f7eac` |
| Property metadata key | `MV_ClusterFull_Visibility_propertyName` | `0x8004e6` |
| Property metadata key | `SV_BordComputer_EgoCar_Slider_propertyName` | `0x810282` |

There are at least **35 distinct `.kzb` resource filename literals**, **35 distinct `_propertyName`-containing strings**, and **68 distinct `_anchorPath`-containing strings** in this executable. The binary also contains the API symbols `eal::api::INode::getProperty`, `eal::api::IProperty::set`, and `switchToNewSceneGraph`, supporting the architecture in which GTF2 resolves scene nodes and updates their properties.

**Crucial evidence boundary:** these strings prove **GTF2 knows about named scene resources, node paths and configurable property names**. They do **not** prove that a particular RTE DP updates a particular node or that a `.kzb` asset was present/loaded in a given runtime. The provided firmware ZIP has image containers, but no directly listed `.kzb` entries; the KZB scene data must be recovered from the appropriate filesystem/image or from runtime traces to prove binding semantics.

A new inventory tool emits virtual addresses and categorized literals from the original ELF:

```sh
python3 tools/fpk1/research/gtf2/inventory_scene_metadata.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-scene-metadata.csv
```

**Targeted next work:** find GTF2 code xrefs to specific metadata strings (e.g. `GearIndicator`, `CarOutline`, `CRUISE_active_bool_propertyName`), trace the node/property lookup and mutation, then join it to the already proven DP handlers. Until such a join is instruction-verified, the scene-event matrix keeps its node/binding columns unresolved.

### Instruction-level scene-node string cross-references: gear indicators and car outline

The GTF2 ELF contains **exact ARM PC-relative literal loads** of four named scene paths. Unlike a raw strings inventory, this establishes concrete GTF2 code sites that consume those names.

| Named node path | String VA | Pointer literal slot(s) | ARM LDR use site(s) |
| --- | --- | --- | --- |
| `MV_ClusterFull.TubeContainer.CenterTube.GearIndicator` | `0x82369b` | `0x2b627c`, `0x5c8a0c` | **`0x2b6588`, `0x5c932c`** |
| `MV_ClusterFull.TubeContainer.RevoTube.GearIndicatorPHEV` | `0x820661` | matching PC-relative literal slots | **`0x2a09d8`, `0x5c613c`** |
| `PV_WarnPopup_CarOutline.GlassPlate.CarOutline` | `0x85cb30` | `0x557b84` | **`0x557a28`** |
| `RV_ClusterFull_Additional.HubContentRevoTube.CarOutline` | `0x8206c6` | matching PC-relative literal slot | **`0x2a0c48`** |

For the main GearIndicator at `0x5c932c`, the loaded string pointer is passed to `0x10e7bc` at `0x5c9330`, and a resulting string object is passed to `0x6343d8` at `0x5c933c`. At `0x2b6588`, the same scene path is likewise passed to `0x10e7bc` at `0x2b6598`, followed by `0x6343d8` at `0x2b65a4`. The CarOutline popup path at `0x557a28` is passed to `0x10e7bc` at `0x557a48`, then to `0x6343d8` at `0x557a54`.

These are **string construction/storage sequences**. The exact semantic role of `0x6343d8` and subsequent object lookup/property setting must still be resolved. Do not label these as a proven `Gear_Display`→`GearIndicator` or `CarOutline_HMI`→`CarOutline` binding merely because the names match. However, the exact use sites provide a practical reverse-tracing anchor to join the previously verified DP handler call graphs to scene metadata.

Reproduce the exact pointer slots and LDR sites with:

```sh
python3 tools/fpk1/research/gtf2/trace_scene_node_xrefs.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-scene-node-xrefs.csv
```

The script verifies that the named null-terminated string exists, that the literal slot holds its exact VA, and that an ARM PC-relative LDR references that slot. It reports **six exact ARM references across four node names**. This is **stronger than a text match but weaker than a property-binding proof**.

### Scene node path configuration: resolved helper 0x6343d8

The three GTF2 scene-name use sites previously documented at `0x5c932c`, `0x2b6588`, and `0x557a28` all pass the string to a **common GTF2-owned helper `0x6343d8`**, rather than directly resolving a scene node. Instruction-level inspection recovers its complete body:

```asm
6343d8  mov  r3,r0
6343dc  add  r0,r0,#0x8c
6343e0  ldrb r2,[r3,#6]
6343e4  orr  r2,r2,#2
6343e8  strb r2,[r3,#6]
6343ec  b    0x10da48
```

**Exact effect:** given a GTF2 object pointer `r0` and a string object `r1`, the helper sets **bit `0x02` of `object[0x06]`** and tail-calls the imported string-assignment thunk `0x10da48` with destination **`object+0x8c`**. It is therefore a **scene-path/string metadata setter**; it is **not** itself a scene node lookup, scene activation, or DP-to-property binding.

Confirmed caller pairs:

| Scene path | String literal slot | GTF2 path-setter call |
| --- | --- | --- |
| `MV_ClusterFull.TubeContainer.CenterTube.GearIndicator` | `0x5c8a0c` | `0x5c933c` |
| same GearIndicator path, second initialization site | `0x2b627c` | `0x2b65a8` |
| `PV_WarnPopup_CarOutline.GlassPlate.CarOutline` | `0x557b84` | `0x557a54` |

The literal slots were checked to contain the actual null-terminated scene paths (`0x82369b` for GearIndicator, `0x85cb30` for popup CarOutline). The caller uses `0x10e7bc` to construct a string object, then `0x6343d8` to store it in an owner-held object, and `0x10f074` to release the temporary string.

**Consequence for interpreting earlier event flags:** the `object+0x06` flags used by some HMI event handlers may refer to object metadata/configuration, not directly to redraw flags. Specifically, this helper sets `+0x06` bit `0x02`, whereas the odometer handler sets `+0x06` bit `0x08` on two other objects. These are distinct bit values; **do not infer they have the same meaning or act on the same class** without following their constructors/vtables.

Reproducible byte-and-call-target verification:

```sh
python3 tools/fpk1/research/gtf2/verify_scene_path_setter.py /path/to/gtf2
```

**Remaining critical join:** identify the object whose `+0x8c` string receives the path, find its consumer that resolves the scene node, and show a concrete DP-driven property mutation on that same object. Until then, named scene-path initialization and the 24 RTE event routes remain two independently proven chains.

### Scene wrapper structure: path metadata and bound receiver are separate fields

The previously recovered scene-path setter and the two-receiver IPC fan-out can now be connected at the **common wrapper data-layout level** (not yet at a concrete scene-node identity).

| Wrapper field | Verified access | Exact effect |
| --- | --- | --- |
| `+0x8c` | `0x6343d8` setter, `0x6218b0` getter | Stores/returns the address of the path-string metadata object |
| `+0xb8` | `0x6218b8` setter, `0x6218cc` getter | Stores/returns the pointer to the runtime receiver object |
| `+0x06`, bit `0x02` | `0x6343e0–0x6343e8` | Set when the path-string field is assigned |
| `+0x06`, bit `0x40` | `0x6218b8–0x6218c4` | Set when the receiver pointer is assigned |

Exact ARM accessor bodies:

```asm
6218b0  add  r0,r0,#0x8c
6218b4  bx   lr
6218b8  ldrb r3,[r0,#6]
6218bc  str  r1,[r0,#0xb8]
6218c0  orr  r3,r3,#0x40
6218c4  strb r3,[r0,#6]
6218c8  bx   lr
6218cc  ldr  r0,[r0,#0xb8]
6218d0  bx   lr
```

The `+0x8c` getter is called by GTF2 diagnostic/logging code, for example at `0x6adbd8` and `0x11e65c`, where the returned object is subsequently accessed as a string (`[r0,#8]`). This supports interpreting the field as path-string metadata, rather than a direct scene node pointer.

**Implication:** the previously proven event fan-out paths (`0x020001e6`, `0x020002d2`) invoke virtual methods through **wrapper+0xb8**, whereas named GearIndicator/CarOutline initialization sites set **wrapper+0x8c**. These are complementary parts of a plausible scene binding lifecycle. However, no evidence yet proves that the specific wrapper at owner offset `0x1f5d0` or `0x1fb00` has any of the named GearIndicator or CarOutline paths. A per-object link requires finding the exact owner-relative initialization site and matching it to the event handler's wrapper offset.

A new verifier, `verify_scene_wrapper_fields.py`, checks **14 exact ARM words** from the original ELF, including both accessors and two path-getter call sites. It was checked locally against the original binary.

```sh
python3 tools/fpk1/research/gtf2/verify_scene_wrapper_fields.py /path/to/gtf2
```

**Next priority:** cross-reference wrapper offsets `0x1f5d0`, `0x1fb00`, and the GearIndicator/CarOutline owner offsets in their constructors; prove their path strings, then trace assignments to `+0xb8` to recover the concrete receiver class and property semantics.

### Proven scene-node identity for two shared telltale/test event receivers

**New evidence:** the two owner-relative wrapper offsets shared by RTE DP events `0x020001e6` (`ActTest_CommonSoftLEDs`) and `0x020002d2` (`TelltaleHMI_Display`) are initialized with **specific named scene nodes**. This resolves the previously unknown scene identities of these two receivers:

| Owner field offset | Scene path configured in constructor | Constructor path assignment | Constructor owner-field store |
| --- | --- | --- | --- |
| `0x1f5d0` | `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht` | `0x5bf68c` string load → `0x5bf6ac` call `0x6343d8` | `0x5bf6dc` loads offset; `0x5bf6f4` stores wrapper pointer |
| `0x1fb00` | `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_BIG` | `0x5bf84c` string load → `0x5bf864` call `0x6343d8` | `0x5bf898` loads offset; `0x5bf8a0` stores wrapper pointer |

The literal strings are at `0x860d54` and `0x860dbb`, via pointer slots `0x5beed4` and `0x5bef14`. The constructor calls the path setter `0x6343d8`, which stores string metadata at `wrapper+0x8c`.

Both event handlers subsequently load these **same owner fields**, call `0x6218cc` to fetch `wrapper+0xb8`, and invoke the receiver's virtual slot 0:

- `0x020001e6` handler `0x5812a8`: owner offset literal `0x581b84` = `0x1f5d0`, and `0x581b88` = `0x1fb00`.
- `0x020002d2` handler `0x586cd0`: owner offset literal `0x587410` = `0x1f5d0`, and `0x587540` = `0x1fb00`.

**Conclusion, supported by the object identity join:** both a normal telltale display event and a common soft-LED actuator-test event are delivered to **the same two Fernlicht (high-beam) scene wrappers**. The two named nodes likely represent different high-beam presentations, but their actual visibility policy and visual changes remain unproven. The event handlers pass the shared event kind `2`, distinct owner-relative state fields, and other arguments to the receiver. Further decoding is needed to say which incoming payload bits or property values turn the indicator on, off, or animate it.

Reproduction against the original GTF2 ELF:

```sh
python3 tools/fpk1/research/gtf2/verify_fernlicht_scene.py /path/to/gtf2
```

This verifier checks exact instruction words, scene strings, pointer literals, and ARM PC-relative LDR use sites. It was executed against the original binary and reported the two verified Fernlicht bindings.

**This is the first per-object, instruction-backed join of an RTE DP event route to concrete named scene nodes** in this research. It is still not a proof of the ultimate property mutation or rendered output.

### Fernlicht event semantics: both routes have identical receiver call arguments

Compared **instruction by instruction** the two scene-wrapper fan-outs already proven for `ActTest_CommonSoftLEDs` (`0x020001e6`, handler `0x5812a8`) and `TelltaleHMI_Display` (`0x020002d2`, handler `0x586cd0`). After accounting for differing PC-relative literal offsets and BL displacements, **both event handlers use the same instructions and arguments** for both Fernlicht wrappers:

| Wrapper / node | Test event call sequence | Normal telltale call sequence | Argument data |
| --- | --- | --- | --- |
| `owner+0x1f5d0` / `Fernlicht` | `0x5812a8–0x5812d8` | `0x586cd0–0x586d00` | `r1=owner+0x1f5cc` |
| `owner+0x1fb00` / `Fernlicht_BIG` | `0x5812dc–0x581304` | `0x586d04–0x586d2c` | `r1=owner+0x1fafc` |

Both call `0x6218cc` to obtain `wrapper+0xb8` and then invoke **receiver virtual slot `+0x00`**. The other inputs are identical **in structure**: `r2=r6`, `r3=2`, stack arguments `[r5,-1,0]`. The handler does **not** test the lamp's incoming value, select an animation, or toggle visibility inline.

**Important nuance:** identical argument setup does **not** imply identical *runtime values* of `r5` and `r6`; they originate upstream in the event dispatcher. A receiver can distinguish the test and normal-display events using the passed event identity, field/state pointer, or other context. The actual receiver implementation and its interpretation of these parameters remain to be resolved.

Verified locally against the original GTF2 ELF. New verifier:

```sh
python3 tools/fpk1/research/gtf2/verify_fernlicht_event_arguments.py /path/to/gtf2
```

**Narrowed conclusion:** the two IPC/DP events do not implement separate hardcoded high-beam drawing logic at their HMI dispatch sites. They **both delegate to the same pair of scene-bound receiver objects**, using the same calling convention and kind-2 event. To determine precisely which payload bit switches on/off or blinks the lamp, trace the origin of `r5/r6` and devirtualize the receiver's slot-0 implementation.

### Resolved exact scene property names for shared Fernlicht events

**Target milestone reached for two RTE DP event routes.** The same constructor that binds the two wrapper objects to scene paths also assigns their **exact property names** through the common helper `0x6343f0`. The helper stores the string in `wrapper+0x78`; the previously recovered path setter `0x6343d8` stores the node path in `wrapper+0x8c`.

| IPC callback | DP ID | Scene node path | Exact property name |
| --- | --- | --- | --- |
| `ActTest_CommonSoftLEDs` | `0x020001e6` | `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht` | **`Fernlicht`** |
| `ActTest_CommonSoftLEDs` | `0x020001e6` | `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_BIG` | **`Fernlicht_BIG`** |
| `TelltaleHMI_Display` | `0x020002d2` | `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht` | **`Fernlicht`** |
| `TelltaleHMI_Display` | `0x020002d2` | `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_BIG` | **`Fernlicht_BIG`** |

Evidence for `Fernlicht`:

- Node path pointer literal at `0x5beed4` → string `0x860d54`, used by call `0x5bf6ac → 0x6343d8`.
- Property name pointer literal at `0x5beed8` → exact string **`Fernlicht`** at `0x860d7b`, used by call `0x5bf6d0 → 0x6343f0`.
- Owner field `+0x1f5d0` used by both event handlers to reach this wrapper.

Evidence for `Fernlicht_BIG`:

- Node path pointer literal at `0x5bef14` → string `0x860dbb`, used by call `0x5bf864 → 0x6343d8`.
- Property name pointer literal at `0x5bef18` → exact string **`Fernlicht_BIG`** at `0x860de2`, used by call `0x5bf88c → 0x6343f0`.
- Owner field `+0x1fb00` used by both event handlers to reach this wrapper.

The setter `0x6343f0` computes `r0=object+0x78` before tail-calling string assignment. The matching constructor uses `0x6343d8` to set the path at `+0x8c`. **This is a code-proven event-to-scene-property-name mapping**, not a claim about how the scene renders the property or what values mean.

Reproduce:

```sh
python3 tools/fpk1/research/gtf2/verify_fernlicht_properties.py /path/to/gtf2
```

Further reverse engineering should stop at this boundary for each event: **IPC field → DP ID → HMI handler → named scene node → exact property name**. Avoid spending time on renderer internals unless the property identity is ambiguous.

### Resolved property: TelltaleHMI_Display DP 0x020002d3 → Laserlight

The next independent DP-to-scene-property trace has been **verified against the original GTF2 ELF**:

| IPC callback | DP ID | Handler | Owner wrapper | Scene node | Exact scene property |
| --- | --- | --- | --- | --- | --- |
| `TelltaleHMI_Display` | `0x020002d3` | `0x586d34` | `owner+0x1f11c` | `MV_ClusterFull.StatusBar.Laserlight` | **`Laserlight`** |

Instruction-backed join:

- Handler `0x586d34` loads owner offset from literal slot `0x58754c`, whose value is **`0x1f11c`**, then calls the wrapper receiver getter `0x6218cc` at `0x586d3c`.
- Constructor `0x5bf4a4–0x5bf4b0` loads the path string via literal `0x5bee9c` (string VA `0x860d09`), then calls `0x6343d8` to assign it to wrapper `+0x8c`.
- Constructor `0x5bf4c8–0x5bf4dc` loads property string via literal `0x5beea4` (string VA `0x860d22`), then calls `0x6343f0` to assign it to wrapper `+0x78`.
- Constructor `0x5bf4c4` loads **`0x1f11c`** from literal slot `0x5beea0`; `0x5bf4ec` stores the configured wrapper pointer to that exact owner field.

This is the same evidence threshold used for `Fernlicht` and `Fernlicht_BIG`: matching owner field, constructor path/property assignments, and HMI event dispatch. The output rendering and numeric value semantics are deliberately out of scope.

Reproduce:

```sh
python3 tools/fpk1/research/gtf2/verify_laserlight_property.py /path/to/gtf2
```

### Event-to-scene-property table with explicit scene root

The scene column below is the **root segment of the exact scene node path**, not a claim about the currently active scene or renderer:

| IPC event | DP ID | Scene root | Node path within scene | Property name |
| --- | --- | --- | --- | --- |
| `ActTest_CommonSoftLEDs` | `0x020001e6` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht` | `Fernlicht` |
| `ActTest_CommonSoftLEDs` | `0x020001e6` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht_BIG` | `Fernlicht_BIG` |
| `TelltaleHMI_Display` | `0x020002d2` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht` | `Fernlicht` |
| `TelltaleHMI_Display` | `0x020002d2` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht_BIG` | `Fernlicht_BIG` |
| `TelltaleHMI_Display` | `0x020002d3` | `MV_ClusterFull` | `StatusBar.Laserlight` | `Laserlight` |

This presentation deliberately separates `scene_root`, `node_path`, and `property_name`. For future rows, if the node path or property has not been instruction-verified, use `unknown` rather than inferring a scene from callback names.

### Additional resolved DP: TelltaleHMI_Display field +0x00 → Fernlicht_AUTO

A previously omitted `TelltaleHMI_Display` field `+0x00` is written to DP **`0x020002ce`**. This DP does not appear as a direct literal in the 24-entry event matrix because the HMI dispatcher computes it by subtracting 4 from the `0x020002d2` comparison value:

```asm
5754e8  ldr r3,[pc,#...]  ; literal 0x020002d2
5754ec  cmp r8,r3         ; direct 0x020002d2 -> 0x586cd0
5754f8  sub r3,r3,#4      ; 0x020002ce
5754fc  cmp r8,r3
575500  bne 0x58a640
575504  b   0x586c40     ; 0x020002ce handler
```

The handler `0x586c40` falls through to `0x586c74` and `0x586ca0`, invoking three separate scene wrappers. The owner-relative offsets are `0x1f5d0`, **`0x1f868`**, and `0x1fb00`. The newly identified `0x1f868` wrapper is configured in the constructor:

- `0x5beef4` → `MV_ClusterFull.StatusBar.Fernlicht_BIG.Fernlicht_AUTO`, assigned by `0x5bf794 → 0x6343d8`.
- `0x5beef8` → **`Fernlicht_AUTO`**, assigned by `0x5bf7c0 → 0x6343f0`.
- `0x5bef08` → owner offset `0x1f868`, used in the constructor's store at `0x5bf7d8`; the same offset appears in the HMI handler's literal slot `0x587414`.

| IPC event | Payload field | DP ID | Scene root | Node path within scene | Exact property |
| --- | --- | --- | --- | --- | --- |
| `TelltaleHMI_Display` | `+0x00` | `0x020002ce` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht` | `Fernlicht` |
| `TelltaleHMI_Display` | `+0x00` | `0x020002ce` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht_AUTO` | **`Fernlicht_AUTO`** |
| `TelltaleHMI_Display` | `+0x00` | `0x020002ce` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht_BIG` | `Fernlicht_BIG` |

**Caution:** this is a **computed-dispatch route**, so an inventory that recognizes only direct `LDR literal → CMP → BEQ` misses it. This is a concrete reason to extend the event catalog scanner to arithmetic comparisons. No rendering/animation semantics are inferred from the `AUTO` name.

Verified locally against the original GTF2 ELF:

```sh
python3 tools/fpk1/research/gtf2/verify_fernlicht_auto_property.py /path/to/gtf2
```

### Arithmetic DP dispatch inventory: 25 additional RTE routes

The original 24-entry RTE DP scanner recognized direct `LDR literal → CMP → BEQ` comparisons. ARM code in the same main HMI dispatcher also **adds/subtracts immediate values to the literal** before comparing to the incoming DP ID. A new scanner, `scan_computed_hmi_dispatch.py`, follows up to seven ARM instructions after a PC-relative load, interprets ARM rotated immediates, and records `CMP r8,r3` with `BEQ` or `BNE + B` targets.

The scan produced **118 computed comparison routes** in the examined dispatcher window (`0x570000–0x577000`). Intersecting those candidates with the **176 independently recovered RTE callback DP IDs** gives **25 additional candidate RTE dispatch routes** absent from the direct-24 table. The intersection was run against the original ELF.

| Computed DP | HMI handler | Computed DP | HMI handler |
| --- | --- | --- | --- |
| `0x0200016b` | `0x57c934` | `0x0200016c` | `0x57cb60` |
| `0x0200016e` | `0x57d010` | `0x02000176` | `0x57d30c` |
| `0x020001bc` | `0x5800e8` | `0x020001da` | `0x580fa4` |
| `0x020001e4` | `0x581240` | `0x020001e8` | `0x58135c` |
| `0x020001ed` | `0x5815c4` | `0x020001f7` | `0x581be8` |
| `0x020001f9` | `0x581d1c` | `0x020001fb` | `0x581eec` |
| `0x020001fe` | `0x5820b4` | `0x02000202` | `0x5822a4` |
| `0x02000217` | `0x583228` | `0x0200021b` | `0x583b98` |
| `0x02000220` | `0x5844d4` | `0x02000291` | `0x5862f0` |
| `0x02000293` | `0x586378` | `0x02000296` | `0x5863fc` |
| `0x0200029a` | `0x5864cc` | `0x020002a1` | `0x5865d4` |
| `0x020002ae` | `0x586754` | `0x020002af` | `0x5867c0` |
| `0x020002ce` | `0x586c40` | | |

The `0x020002ce` route is already proven to lead to the `MV_ClusterFull` scene properties `Fernlicht`, `Fernlicht_AUTO`, `Fernlicht_BIG`; all **other newly enumerated computed routes still have `scene=unknown`, `node=unknown`, `property=unknown`** until the exact wrapper constructor and event handler are joined.

**Reproduce:** generate a newline-separated list of the 176 DP IDs from the existing RTE write scanner, then run:

```sh
python3 tools/fpk1/research/gtf2/scan_computed_hmi_dispatch.py /path/to/gtf2 \
  --dp-ids /path/to/rte-dp-ids.txt --csv \
  > build_fpk1/research-artifacts/gtf2-computed-rte-dispatch.csv
```

**Verification boundary:** this scanner checks literal values, immediate arithmetic and target branches. It does not do complete ARM control-flow analysis across conditionally skipped instructions; rows should be treated as static dispatch candidates until their local branch preconditions are checked. No scene-property identity should be inferred from a DP's IPC callback name alone.

### Resolved property: TelltaleHMI_Display DP 0x020002cd → ESP

The direct DP handler `0x586bf0` uses owner offset `0x453b8` via literal slot `0x587544`. The same owner offset is stored by the scene wrapper constructor at `0x294658–0x29465c` via literal slot `0x293ef4`. The constructor sets:

- Node path literal slot `0x293ee8` → **`MV_ClusterFull.StatusBar.line1_auchEarlyWelcome.ESP`**, string setter call `0x29461c → 0x6343d8`.
- Property literal slot `0x293ef0` → **`ESP`**, property setter call `0x294648 → 0x6343f0`.
- Handler receiver getter call `0x586bfc → 0x6218cc`.

| IPC event | DP ID | Scene | Node path within scene | Property |
| --- | --- | --- | --- | --- |
| `TelltaleHMI_Display` | `0x020002cd` | `MV_ClusterFull` | `StatusBar.line1_auchEarlyWelcome.ESP` | **`ESP`** |

**Reproduced successfully against the original GTF2 ELF** with `verify_esp_scene_property.py`, which checks the exact ARM instruction words, string literal values, PC-relative LDR references, and setter/getter branch destinations. As elsewhere, scene root comes from the path, not from a runtime active-scene observation.

```sh
python3 tools/fpk1/research/gtf2/verify_esp_scene_property.py /path/to/gtf2
```

### Automated scene wrapper/property join and coverage audit

A new **whole-binary constructor-to-HMI join** removes the need to manually reverse engineer every property one at a time. `join_scene_wrapper_properties.py` scans for:

1. `BL 0x6343d8`: path-string setter (`wrapper+0x8c`).
2. Nearby `BL 0x6343f0`: property-name setter (`wrapper+0x78`).
3. Owner-relative wrapper pointer store through `STR r0,[r4,rN]` and a PC-relative owner offset literal.
4. HMI code `LDR r3,=owner_offset; LDR r0,[r4,r3]; BL 0x6218cc`, proving a use of the same wrapper.
5. Conservative string validation: the property name must equal the last component of the node path. Nonmatching names are excluded rather than guessed.

A first local scan against the original GTF2 ELF found **47 unique owner-relative scene wrappers referenced by this HMI getter pattern**, across **241 HMI use sites** (including many unrelated to the 49 RTE event routes). The broad constructor pass produced 1,278 candidate owner offsets, but these are **not all validated RTE event bindings**. The 47-object join is a conservative subset and can still include false-positive constructor proximity matches; individual property links need independent confirmation if the property name differs from the path component.

Intersecting those HMI uses with the 49 known RTE routes, using conservative handler windows, yields **12 distinct DP routes** with at least one matched scene property. Examples beyond the earlier manually proven properties:

| IPC callback | DP ID | Scene | Node within scene | Property | HMI use |
| --- | --- | --- | --- | --- | --- |
| `ActTest_SoftLEDs` | `0x020001ea` | `MV_ClusterFull` | `StatusBar.Motorlauflampe` | `Motorlauflampe` | `0x5813ec` |
| `HVK_01` | `0x020001fe` | `MV_ClusterFull` | `StatusBar.ChargeIndicator` | `ChargeIndicator` | `0x5820e8` |
| `HVK_01` | `0x020001fe` | `MV_ClusterFull` | `StatusBar.EVMode` | `EVMode` | `0x582114` |
| `HVK_01` | `0x020001fe` | `MV_ClusterFull` | `StatusBar.Rekuperation` | `Rekuperation` | `0x582140` |
| `ActTest_CommonSoftLEDs` | `0x02000200` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht_AUTO` | `Fernlicht_AUTO` | `0x582200` |
| `ActTest_CommonSoftLEDs` | `0x02000201` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht_BIG` | `Fernlicht_BIG` | `0x582274` |
| `TelltaleHMI_Display` | `0x0200021d` | `MV_ClusterFull` | `StatusBar.Fernlicht_BIG.Fernlicht` | `Fernlicht` | `0x583ff0` |

These are **static owner-offset/constructor joins**, not proof that the named property is changed for every possible payload value. The `HVK_01` DP fans out to several hybrid/EV status objects, showing why a one-DP-one-property table is inadequate.

The local audit also generated a **176-write inventory** with scene/property columns: 180 CSV data rows after expanding one-to-many joins, **12 distinct DP IDs with at least one automatically resolved scene property**. The other IDs remain `unknown` or may use other dispatch mechanisms, different getter patterns, or non-Kanzi state updates.

Reproduce the verified wrapper-use inventory:

```sh
python3 tools/fpk1/research/gtf2/join_scene_wrapper_properties.py /path/to/gtf2 --csv \
  > build_fpk1/research-artifacts/gtf2-scene-wrapper-uses.csv
```

**Outstanding completeness limits:** this scanner handles the common `[r4,r3]` getter pattern only. It does not recover every virtual call, nested/indirect property binding, scene resource, or non-RTE IPC event. Do not claim full event-to-scene coverage based on the 47 wrappers or 12 DP routes. Continue by extending handler control-flow recovery and alternate wrapper-access patterns, retaining `unknown` until each link is proven.

### Expanded property join: receiver owner register r0 or r4

The first automatic join was too narrow: it only recognized `LDR r0,[r4,r3]; BL 0x6218cc`. Several real handlers (including the independently verified `ESP` mapping) obtain their owner from a helper and use **`LDR r0,[r0,r3]`** instead. The join tool now scans backward from every `BL 0x6218cc` and accepts both owner base registers, while requiring the same exact constructor owner offset, path/property strings, and property setter.

**Measured on the original GTF2 ELF:**

- **691 candidate receiver-getter call sites** linked to constructor metadata.
- **126 distinct owner-relative wrapper offsets** with a scene path and property name.
- When intersected with the known 49 RTE dispatch handlers using a bounded local instruction window, **85 candidate handler-to-property rows**, covering **33 distinct DP IDs** and **36 distinct property names**.

These are **candidate handler-local joins** until each handler's precise CFG boundaries and source register provenance are checked. The getter/constructor field identity itself is stronger evidence. The scanner still excludes properties whose names differ from the final node path component.

New representative **candidate** mappings:

| DP ID | Callback provenance | Scene root | Node suffix / property |
| --- | --- | --- | --- |
| `0x02000216` | `TelltaleHMI_Blink` | `RV_ClusterFull_Additional` | `FAS_Cluster.FAS_Cluster.Limiter` / `Limiter`; `Limiter_shadow`; `Cruise_shadow` |
| `0x0200021f` | `TelltaleHMI_Blink` | `RV_ClusterFull_Additional` | `Limiter`; `Limiter_shadow`; `LIMorGRA_Speed` |
| `0x02000220` | arithmetic route | `RV_ClusterFull_Additional` | `praediktivesACC`; `PEA_Foot`; `ACC_STA` |
| `0x020002ae` | arithmetic route from `CarOutline_HMI` | `RV_ClusterFull_Additional` | `HubContentRevoTube.CarOutline.CarOutline` / `CarOutline` |
| `0x02000296` | arithmetic route | `MV_ClusterFull` | `StatusBar.line1_auchEarlyWelcome.TirePressure` / `TirePressure` |
| `0x020002cd` | `TelltaleHMI_Display` | `MV_ClusterFull` | `StatusBar.line1_auchEarlyWelcome.ESP` / `ESP` (previously independently verified) |

The new scene root `RV_ClusterFull_Additional` is now recovered from the exact GTF2 scene-node path strings, in addition to `MV_ClusterFull`. The handler calls remain kind-2 event notifications; no rendered behavior is inferred.

**Coverage accounting must remain explicit:** 33 of the 49 RTE dispatch routes have *candidate* property joins; this does not imply all 176 RTE DP writes have been traced, and it does not imply the 36 property names exhaust the scene. For each unjoined event the output remains `unknown`. The user's requested endpoint is scene root + node path + property name, not Kanzi rendering internals.

### Whole 176-DP source inventory: scene root/property coverage status

A full local CSV has been generated for **all 176 unique RTE DP writes** recovered from GTF2. One-to-many event-to-property relationships expand the final CSV to **233 rows**. The matrix retains callback name, payload offset/width, DP ID, handler, scene root, complete node path, exact property name, evidence level, write VA, and event-use VA.

- **176 / 176** unique source DP IDs represented, from **33 named IPC callback types plus unknown**.
- **33 / 176** DP IDs have at least one **candidate scene/property join** through the currently recognized HMI dispatch/getter pattern.
- **143 / 176** DP IDs remain **unknown** at the scene/property level. This is an actual coverage gap, not evidence that they have no scene effect.
- Two observed scene roots among resolved rows: **`MV_ClusterFull`** and **`RV_ClusterFull_Additional`**.
- The full matrix includes **36 distinct property names** among the candidate handler joins. Some independently proven properties such as `Laserlight` have previously verified per-event documentation and must be merged separately if a generic scanner misses their specific receiver pattern.

The local full matrix deliberately distinguishes `candidate:constructor-owner+handler-local-getter` from `dp-write-only`. A name is not inferred merely from an IPC callback name. A bounded handler window can include nearby branches, so each new mapping should be promoted to independently verified only after checking its exact handler control-flow and wrapper initialization.

**Important research correction:** the 49 main-dispatch routes are only a subset of the 176 RTE DP writes. The remaining DP IDs may be consumed through another dispatcher, a direct state reader, a computed event transform, or a path not covered by the scanner. They must not be classified as unused without an additional search.

For the requested full picture, keep this inventory as the authoritative **coverage ledger**: every source event exists as a row even when its scene/property remains `unknown`. Do not claim that the project has completely reconstructed all event semantics until those 143 gaps have been resolved or explicitly shown to be non-scene events.


## Сводная архитектура внешнего IHmiKss и границы доказанного (2026-10-28)

Этот раздел является **общей точкой интеграции** результатов исследований callback/proxy/ThreadMan; отдельные заметки остаются журналом доказательств, но не должны подменять полную схему. Источник: стоковый `gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

### 1. Проверенная цепочка и границы

| Уровень | Установлено статическим анализом | Ещё неизвестно |
|---|---|---|
| Внешний интерфейс | В коде `0x6939b4` используются дескрипторы `asi.gss.ipc.rte.hmi.IHmiKss` (`0xa7f838`) и `IHmiKssReply` (`0xa7f83c`); вызывается импортированный `comm::Proxy::Proxy` (`0x10ebe8`) | Wire method ID, сериализация и маршрутизация конкретного входящего сообщения |
| Экземпляры | `0x68ee80` создаёт два callback-объекта через `0x69780c`, аргументы экземпляров 1 и 2; оба имеют первичную vtable `0x88e6b8`; `0x697e94` настраивает каждый | Как экземпляры выбираются удалённой стороной |
| Связь proxy/callback | `0x697e94` вызывает `0x6939b4` и передаёт основной объект и отдельно `object+4`; `0x6939b4` сохраняет исходный callback в поле `+0x48` выделенного коммуникационного объекта (`0x693c50`) | Чтение этого поля входящим диспетчером и конкретный virtual call |
| Lifecycle | `object+4` имеет вторичную vtable `0x88e910`, передаётся как `comm::LifecycleListener*`; её слот 3 через `0x698014` вызывает `0x697e94` | Какое состояние `comm` вызывает этот слот |
| RTE completion | **Первичная** vtable слот 136 (`0x88e8d8`) → `0x693ff0` → селектор `0x2afa` | Кто вызывает первичный слот 136; wire callback это или локальное completion-уведомление |
| Внутренняя доставка | `0x2afa` поступает в индекс 3 `/eMsgBoxIDThreadManager`; локальная pthread FIFO; обработчик `0x12dfb0` | Не требуется моделировать как отдельный внешний QNX IPC endpoint |
| Stage3 | `0x13076c` проверяет DP `0x02000236` (байт 2), затем `0x020002bb` (171); путь Stage3 через `0x699594`, иначе немедленный старт | Порядок внешних событий в реальном runtime |
| HMI | 176 DP ID в прежней переписи, 49 основных маршрутов, 33 кандидатных DP→scene join и 143 ещё не сопоставленных | Полное покрытие всех свойств сцены и подтверждение candidate CFG |

**Разные пространства идентификаторов:** индекс vtable 136, внутренний селектор `0x2afa`, номер локального канала 3, номер экземпляра 1/2 и внешний IPC method ID **не взаимозаменяемы**. Не назначать method ID по совпадению чисел.

### 2. Что нового подтверждено при интеграции

В исходном ELF есть точные диагностические строки **`HmiCommKssReplyImpl rteNoInit %d`** (VA `0x88ec08`), **`HmiCommKssReplyImpl rteTimeout %d`** (VA `0x88eed4`) и **`HmiCommKssReplyImpl lost server connection, reactivating...`** (VA `0x88f521`). Прямые адресные ссылки на них найдены соответственно в литералах `0x693d8c`, `0x694200` и `0x698054`. Последняя строка используется в `0x69801c` перед переходом к `0x697e94`. Это подтверждает смысл **реактивации при потере соединения**, а не гарантированное уведомление об успешном подключении. Наличие отдельных `rteNoInit` и `rteTimeout` показывает, что их нельзя сворачивать в единое событие `RTEUpdateDone` без проверки call graph.

Проверка `0x693c40..0x693cd0` подтверждает сохранение указателя основного callback в `[r5+0x48]` **до** вызова конструктора `comm::Proxy`; при этом `object+4` отдельно передаётся как listener. Это важное структурное доказательство, но чтение `+0x48` диспетчером ещё не найдено.

### 3. Практический контракт для эмулятора: что можно и нельзя считать установленным

**Можно:** считать `IHmiKss/IHmiKssReply` реальной парой интерфейсов, различать два callback-экземпляра, моделировать отдельные события DP-init и RTE-update completion, а внутреннюю очередь ThreadMan реализовать как локальный FIFO, не как внешний IPC. Для startup учитывать оба DP-гейта `0x02000236` и `0x020002bb`.

**Нельзя пока:** объявлять, что отправка внешнего сообщения с ID 136 или `0x2afa` вызывает готовность HMI; утверждать, что вторичный `LifecycleListener` вызывает completion; считать 176 DP-ID полным протоколом; считать 33 кандидатных join подтверждённой полной картой сцены.

### 4. Оставшийся блокирующий эксперимент

Вместо дальнейшего линейного перечисления адресов: **найти конкретное чтение поля callback `+0x48` в методах коммуникационного объекта, установить виртуальную цель и её входной message descriptor**. Параллельно проверить обработчики `rteNoInit`, `rteTimeout` и reactivation на отдельные переходы состояния. Если внешний dispatch находится в `comm` shared library, потребуется анализ соответствующей библиотеки из firmware, а не бесконечное расширение локального call graph `gtf2`.

Связанные подтверждающие документы: `gtf2-hmicomm-two-callback-instances.md`, `gtf2-callback-instances-comm-proxy.md`, `gtf2-ihmikss-proxy-descriptor-proof.md`, `gtf2-ihmikss-proxy-lifecycle-listener.md`, `gtf2-threadman-message-send-receive.md`, `gtf2-message-box-pthread-fifo-implementation.md`.


## Архив точных доказательств, перенесённых из коротких заметок

Ниже сохранены исходные адреса, листинги и оговорки из отдельных файлов; после переноса их можно удалить без потери сведений.


### Перенесено из `gtf2-hmicomm-two-callback-instances.md`

# Two callback-object instances created in HmiComm setup

Stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This extends the earlier callback-object ownership analysis and matters for external method routing. The 148-entry vtable at `0x88e6b8` and slot 136 at `0x88e8d8` were already established.

## Constructor loop, not a singleton callback instance

In `0x68ee80`, `r7` starts at 1 (`0x68ee90`). The loop at `0x68eea8` creates an object via `0x69780c`, passing `r1=r7` at `0x68eeb0..0x68eeb4`. It stores the resulting 12-byte shared-pointer record into a growable vector in owner `r4` at offsets `+4,+8,+0xc`. At `0x68f19c`, the counter is compared against 3, and `0x68f1a0 BNE 0x68eea8` repeats for counter 2. Therefore **two** objects are constructed with arguments **1 and 2**.

Constructor `0x69780c` allocates 52 bytes and calls `0x6977a4`; `0x6977b8 STR r1,[r4,#0xc]` stores the supplied instance argument at offset `+0xc`. The constructor sets the primary vptr `0x88e6b8` at `+0`. The two instances share this same callback table and hence both have virtual slot 136 -> `0x693ff0`.

At `0x68f1a4..0x68f1b0`, after the loop, `0x68ee80` calls a **different** constructor `0x690a80` and appends its result to a **different** vector at owner offsets `+0x1c,+0x20,+0x24`. It must not be counted as a third `0x69780c` instance.

## Implication for RTEUpdateDone dispatch

The slot-136 function `0x693ff0` uses `r0` only as an unused incoming instance argument: it sets `r1=3`, `r2=0x2afa`, constructs and sends the ThreadMan completion message. Thus the **same implementation** can be called on either object instance, and the instance's `+0xc` value does not select the internal channel in this function.

The actual external ASI method descriptor -> which instance -> vtable slot mapping is still **unproven**. It would be wrong to infer a unique method ID or a unique callback object from the vtable address alone.

## Nearby setup context

The same `0x68ee80` setup calls `0x693294` with owner+0x48 and `0x6921cc` with owner+0x80 before constructing the two callback objects. Later it performs additional setup and reports `HmiComm ready.` (stock literal `0x88d2b9`). The existence of this message in the function does not establish a runtime timestamp.

## Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68ee80 --stop 0x68ef00
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68f170 --stop 0x68f1c4
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6977a4 --stop 0x697848
```



### Перенесено из `gtf2-callback-instances-comm-proxy.md`

# HmiComm callback instances connect to a comm::Proxy constructor

Verified in stock GTF2 ELF (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`) by disassembling executable PT_LOAD and resolving PLT entries through original ELF `R_ARM_JUMP_SLOT` relocations. Builds on `gtf2-hmicomm-two-callback-instances.md` and does not re-claim discovery of the callback vtable.

## Per-instance processing after construction

`0x68ee80` first creates two `0x69780c` callback objects with instance arguments 1 and 2 and stores them in the owner vector. Later it iterates that vector:

```asm
68f31c ldr r3,[r5]
68f320 ldr r6,[r3,#8]    ; vector end
68f328 ldr r0,[r6,#-8]   ; current shared-pointer's object
68f32c bl 0x697e94
68f330 ldr r3,[r5]
68f338 add r6,r6,#12     ; 12-byte vector entry
68f33c ldmib r3,{r0,r2}  ; vector start/end metadata
68f348 bne 0x68f328
```

`0x697e94` requires non-null object fields `+0x28` and `+0x2c`, reads the stored per-instance value at `+0xc` (`0x697ee0`), and passes it along with the object pointer and associated shared-pointer record into `0x6939b4` at `0x697f1c`. The call `0x697d04` prepares object-related state before that operation. **This is a per-instance setup/activation path, not simply object construction.**

## Dynamic-symbol resolution identifies communication library boundary

Within `0x6939b4`, a 108-byte object is allocated (`0x693be4`), initialized (`0x693c00`), and passed to `0x10ebe8` at `0x693cd0`. The imported symbol is exactly:

```cpp
comm::Proxy::Proxy(
    comm::TrackedBase::IdentityArgs const&,
    comm::ServiceRegistration const&,
    comm::InterfaceStyle,
    comm::LifecycleListener*)
```

ELF evidence: PLT `0x10ebe8` maps to GOT `0xa6577c`; `R_ARM_JUMP_SLOT` relocation index 434, dynamic symbol index 572, mangled name `_ZN4comm5ProxyC2ERKNS_11TrackedBase12IdentityArgsERKNS_19ServiceRegistrationENS_14InterfaceStyleEPNS_17LifecycleListenerE`.

Other relevant resolved imports:

| PLT VA | Dynamic symbol |
|---|---|
| `0x10e27c` | `comm::LifecycleImpl::LifecycleImpl(comm::Lifecycle::State, comm::LifecycleListener*)` |
| `0x10df10` | `ipl::UUID::UUID(ipl::UUID const&)` |
| `0x10e21c` | `util::SharedPtrDefaultBase::SharedPtrDefaultBase(util::SharedPtrDefaultBase const&)` |
| `0x10e468` | `atomic_add_value` |

This is the first identified **`comm::Proxy` constructor** in the per-instance callback setup chain. It supplies a concrete place to recover `ServiceRegistration`, interface UUID and lifecycle semantics. Do not call the constructor itself a successful external subscription.

## Relationship to ThreadMan RTEUpdateDone

The existing callback vtable `0x88e6b8` contains slot 136 -> `0x693ff0`, which sends `0x2afa` through the process-local `/eMsgBoxIDThreadManager` pthread FIFO. Both instances share the table. The `comm::Proxy` setup is **upstream infrastructure** but does not yet establish the external method ID, which instance receives the call, or exact method dispatch mapping.

## Next proof targets

1. Decode `ServiceRegistration` argument and interface UUID supplied to `comm::Proxy`.
2. Find the actual dispatch path from `comm::Proxy`/interface object to callback slot 136.
3. Determine whether `0x693ff0` is a lifecycle notification rather than a wire-method callback. Its position in the large vtable alone cannot distinguish these.



### Перенесено из `gtf2-ihmikss-proxy-descriptor-proof.md`

# IHmiKss descriptor in per-instance proxy setup

Original stock `gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

The `0x6939b4` setup routine called from `0x697e94` for each of the two callback objects uses the actual `IHmiKss` and `IHmiKssReply` interface descriptors.

| Address | Value | Interpretation |
|---|---|---|
| `0x693d30` | `0xa7f838` | descriptor pointer loaded at `0x693ab0` |
| `0xa7f838` | `0x88f55d` | exact string `asi.gss.ipc.rte.hmi.IHmiKss` |
| `0x693d44` | `0xa7f83c` | descriptor pointer loaded at `0x693bb0` |
| `0xa7f83c` | `0x88f579` | exact string `asi.gss.ipc.rte.hmi.IHmiKssReply` |

The first string pointer is dereferenced at `0x693ac8` and stored in a stack-local registration structure at `0x693b08`. The second is dereferenced at `0x693bc0` and stored at `0x693bc4`. The same routine invokes `comm::Proxy::Proxy` through PLT `0x10ebe8` at `0x693cd0`.

Proven chain: `HmiComm 0x68ee80` -> two callback instances via `0x69780c` -> per-instance setup `0x697e94` -> `0x6939b4` -> `IHmiKss/IHmiKssReply` descriptor construction and `comm::Proxy`.

This proves interface identity, **not** external wire-method identity. Callback vtable slot 136 (`0x693ff0`) still has no verified external ASI method ID or name, and runtime invocation timing is unknown. The vtable slot index 136, ThreadMan selector `0x2afa`, and internal message-box index 3 are separate numbering spaces.

Reproduce using `tools/fpk1/research/gtf2/disassemble_ptload.py` ranges `0x693ab0..0x693bd0` and `0x693ca8..0x693cd4`, and inspect the four ELF addresses listed above.


### Перенесено из `gtf2-ihmikss-proxy-lifecycle-listener.md`

# Distinguish primary IHmiKss callback dispatch from comm::Proxy LifecycleListener

Stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Direct original ELF disassembly and pointer reads. Extends `gtf2-ihmikss-proxy-descriptor-proof.md`, avoiding the previously repeated primary vtable discovery.

## The actual fifth constructor argument is the secondary subobject

At `0x697e94`, the two per-instance callback objects enter setup. The call to `0x6939b4` at `0x697f1c` passes `r0=sp+8`, `r1=object[+0xc]`, `r2=object`, `r3=sp+20`, **fifth argument `[sp]=object+4`** (`0x697f0c ADD r12,r4,#4`; `0x697f10 STR r12,[sp]`). The wrapper `0x6939b4` saves the incoming fifth argument, then at `0x693cb0 LDR lr,[sp,#0xd8]` and `0x693cc4 STR lr,[sp]` passes it unchanged as the fifth argument to imported `comm::Proxy::Proxy(IdentityArgs const&, ServiceRegistration const&, InterfaceStyle, LifecycleListener*)` at `0x693cd0`. The register `r3=0` at `0x693cac` is the fourth argument `InterfaceStyle`; `r2=sp+0x98` points to registration data.

In the constructor `0x6977a4`, `0x6977c8 STM r4,{r2,r3}` writes **primary vptr `0x88e6b8` to object+0**, **secondary vptr `0x88e910` to object+4**. Therefore the exact `LifecycleListener*` passed to `comm::Proxy` is **the secondary polymorphic subobject at object+4**, not the primary 148-entry method table.

## Secondary listener table and concrete re-entry

The secondary table at `0x88e910` contains four function pointers:

| Secondary slot | Pointer VA | Target | Verified behavior |
|---:|---|---|---|
| 0 | `0x88e910` | `0x69387c` | this-adjusting destructor thunk |
| 1 | `0x88e914` | `0x6937fc` | this-adjusting thunk to `0x693804` |
| 2 | `0x88e918` | `0x693774` | this-adjusting no-op thunk to `0x69377c` |
| **3** | **`0x88e91c`** | **`0x698014`** | subtracts 4 from `this`; jumps to `0x69801c` -> `0x697e94` |

ARM proof: `0x698014 SUB r0,r0,#4`; `0x698018 B 0x69801c`; `0x698044 MOV r0,r4`; `0x69804c B 0x697e94`. The intervening code `0x69801c..0x698044` includes a conditional logging call and preserves the object pointer.

**Meaning:** a method on the actual `LifecycleListener` interface can re-enter the per-instance proxy setup routine. This is a concrete lifecycle callback behavior. It does not establish which library lifecycle state causes the call, nor whether repeated calls create a new proxy or return early; `0x697e94` has guards at entry.

## Primary slot 136 is a different interface slot

The **primary** vtable `0x88e6b8` slot 136 (`0x88e8d8`) points to `0x693ff0`, which constructs `eSIDThreadManRTEUpdateDone` selector `0x2afa` on internal channel 3. It is **not** the `LifecycleListener` method at secondary slot 3, nor is primary slot 136 a proven external ASI wire method ID. The primary callback object's `this` at `+0` and secondary listener subobject at `+4` must not be conflated.

The data at `0x88e908` and `0x88e90c` are RTTI-related vtable header words (`-4`, zero); `0x88e910` is the actual secondary address point. A further subobject address point exists at `0x88e928` (object+8), also distinct.

## Updated topology

```text
IHmiKss callback object (two instances, instance IDs 1 and 2)
  +0  primary vptr 0x88e6b8
       slot 136 -> 0x693ff0 -> internal ThreadMan RTEUpdateDone
  +4  secondary vptr 0x88e910
       passed to comm::Proxy as LifecycleListener*
       secondary slot 3 -> 0x698014 -> 0x69801c -> 0x697e94
         -> 0x6939b4 -> comm::Proxy constructor
  +8  further vptr 0x88e928
  +0xc instance ID
```

This **resolves the direct lifecycle-listener-vs-primary-slot ambiguity**, but does not yet recover the external method descriptor/dispatch mapping for primary slot 136. Next examine `comm::Proxy` registration and how the library invokes primary vtable methods, especially whether slot 136 represents an inbound wire event or a completion callback from another proxy operation.

Reproduce: disassemble `0x6977a4..0x6977cc`, `0x697e94..0x697f20`, `0x693ca8..0x693cd4`, `0x698014..0x698050`; read 4-byte pointer values at `0x88e910..0x88e91c`.



### Перенесено из `gtf2-message-box-pthread-fifo-implementation.md`

# GTF2 named message boxes: in-process pthread FIFO

Verified against original stock `gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This resolves the transport ambiguity in `gtf2-threadman-named-message-box.md`.

The channel named `/eMsgBoxIDThreadManager` (index 3) is implemented in the process by linked heap nodes, a mutex and a condition variable. It is **not** a POSIX `mq_open` endpoint. ARM PLT imports were resolved through original ELF relocation and symbol tables.

| Function | Relevant PLT imports | Key operations |
|---|---|---|
| `0x68d060` send | `malloc` `0x10e7ec`; `memcpy` `0x10dbd4`; `pthread_mutex_lock` `0x10dcdc`; `pthread_cond_signal` `0x10f140`; `pthread_mutex_unlock` `0x10d808` | Allocates `length+8` node, stores next=0 and length, copies payload to node+8, checks capacity, appends FIFO node, increments count, signals waiter |
| `0x68cf00` receive | `pthread_mutex_lock` `0x10dcdc`; `pthread_cond_wait` `0x10dcf4`; `pthread_mutex_unlock` `0x10d808`; `memcpy` `0x10dbd4`; `free` `0x10e2c4` | Waits while empty, checks destination buffer length, removes head, decrements count, copies payload, frees node, returns message length |
| `0x68d308` create | `strlen` `0x10edd4`; `strcmp` `0x10f1e8`; `strcpy` `0x10d88c` | Maintains local named-slot table |

Machine-code anchors: `0x68d0a0` malloc; `0x68d0d8` node header; `0x68d0e0` memcpy; `0x68d0e8` mutex lock; `0x68d1a0` append tail; `0x68d1a8` set head if empty; `0x68d1d4` cond signal; `0x68d1f0` count increment; `0x68d1f4` mutex unlock. Receiver `0x68cf44` lock; `0x68cf98` cond wait; `0x68cfd0` read node length; `0x68cfd4` capacity compare; `0x68cff8` advance head; `0x68d01c` decrement count; `0x68d020` unlock; `0x68d030` copy; `0x68d038` free.

Static end-to-end: callback vtable slot 136 `0x693ff0` sends selector `0x2afa` to channel index 3 -> `/eMsgBoxIDThreadManager` -> bounded pthread FIFO -> ThreadMan `0x69b29c` receives from same index 3 -> `0x12dfb0` dispatches `eSIDThreadManRTEUpdateDone` -> DP guard checks -> delayed/Stage3/immediate HMI startup.

**Not yet established:** external ASI `IHmiKss` method name for slot 136, actual runtime callback timing or successful delivery. The internal message-box channel and external ASI IPC are separate mechanisms.

Reproduce with `tools/fpk1/research/gtf2/disassemble_ptload.py` ranges `0x68d060..0x68d200`, `0x68cf00..0x68d050`, and `0x68d308..0x68d4c4`.


### Перенесено из `gtf2-rte-completion-callback-slot.md`

# RTEUpdateDone producer is slot 136 of the already-recovered IHmiKss callback table

Verified against the original stock `STAGE2.1/bin/gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This resolves the indirect entry of `0x693ff0` left open in `gtf2-threadman-producers-and-startup-dp-writers.md`. The table itself and callback object construction were already established in `gtf2-callback-object-vptr-and-caller.md`; **do not count them as new discoveries**.

## Exact indirect function pointers

Scanning the entire original ELF for little-endian absolute pointers to the two functions finds one occurrence each:

| Table base | Slot index (zero-based) | Pointer slot VA | Target | Meaning |
|---|---:|---|---|---|
| `0x88e6b8` | **96** | `0x88e838` | `0x694358` | `payload[3]` to DP `0x02000236` via tail branch `0x131390` |
| `0x88e6b8` | **136** | `0x88e8d8` | `0x693ff0` | create `eSIDThreadManRTEUpdateDone` (selector `0x2afa`) |
| `0x88e6b8` | **137** | `0x88e8dc` | `0x693fdc` | write constant `171` to DP `0x020002bb` via tail branch `0x13143c` |

These are entries in the **same 148-entry callback pointer table** already associated with the 52-byte object constructed by `0x6977a4`. The pointer to `0x693ff0` is not a direct `BL` callsite; therefore the earlier zero-direct-call observation is fully explained by indirect dispatch. The exact external ASI method index / IPC method name for slot 136 is **not yet proven**. Slot adjacency to the DP writer at index 137 does not prove those two callbacks execute consecutively.

The 148-entry table ends at index 147 (`0x88e904 -> 0x694024`). Following words at `0x88e908` are **not** further entries of this same table; they begin a separate data/vtable region.

## Machine code at the producer

```asm
693ff0 push {r0,r1,r4,lr}
693ff4 movw r2,#0x2afa
693ff8 mov r1,#3
693ffc mov r0,sp
694000 bl 0x12ca9c
694004 mov r0,sp
694008 bl 0x12c994
69400c mov r0,sp
694014 bl 0x12c9fc
694018 pop {r2,r3,r4,pc}
```

`0x12c994` checks the local wrapper's byte `+4` and calls `0x69b4ac` on its pointer `+0`; `0x69b4ac` uses GTF2 IPC/message transport helpers `0x68d7f8`, `0x68d570`, `0x68d060` and checks a `-1` failure result. The consumer `0x69b29c` calls `0x68d7f8`, `0x68d570`, `0x6abf20`, then `0x68cd70` / `0x68ce1c` / `0x68cf00` to receive a message into an object buffer at `+0x10`. This strengthens the message transport link but does not establish the concrete transport endpoint or serialization contract.

## Reconciled application-level chain

```text
IHmiKss callback object [vptr 0x88e6b8]
  + slot 136 -> 0x693ff0
      -> construct 0x2afa message
      -> 0x12c994 -> 0x69b4ac (send-like IPC transport)
ThreadMan run 0x12e380
  -> 0x12e0a8 -> 0x69b29c (receive-like IPC transport)
      -> 0x12dfb0 (processMessage)
          -> eSIDThreadManRTEUpdateDone
          -> 0x130510 / 0x13076c / 0x13080c
          -> conditional HMI startup / Stage3 path
```

**Important distinction:** A callback table pointer is evidence of a registered callable implementation, not proof of the external method number, registration timing, or a specific runtime callback invocation. Recover those by tracing the interface descriptor and dispatch registration rather than assigning a name based solely on index.

## Reproduction

```python
import struct
blob = open('gtf2', 'rb').read()
for target in (0x693ff0, 0x694358, 0x693fdc):
    needle = struct.pack('<I', target)
    matches = []
    off = 0
    while (off := blob.find(needle, off)) >= 0:
        matches.append(hex(off + 0x100000))
        off += 1
    print(hex(target), matches)
```

Original executable LOAD has VA base `0x100000` and file offset zero for these pointer slots. This scan yields `0x88e8d8`, `0x88e838`, `0x88e8dc` respectively.

Next: trace the method descriptor corresponding to slot 136, and inspect `0x68d060`/`0x68cf00` transport operations without assuming that callback slot indices equal ASI IPC method IDs.



### Перенесено из `gtf2-rte-completion-stage3-join.md`

# ThreadMan RTEUpdateDone branch joins existing Stage3 startup path

Source: stock `STAGE2.1/bin/gtf2` (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`). This is an **integration/correction** to `gtf2-threadman-completion-events.md` and the already documented `gtf2-lifecycle.md` Stage3 chain, not a new Stage3 function discovery.

## Concrete RTE completion branch

`0x12dfb0` handles the internal event `eSIDThreadManRTEUpdateDone` (selector `0x2afa`). At `0x12e03c` it tests the per-run completion flag and, if unset, executes:

```asm
12e048 add r5,sp,#4
12e04c add r2,r4,#0xf8
12e050 add r1,r4,#8
12e054 mov r0,r5
12e058 bl  0x130510
12e05c mov r0,r5
12e060 bl  0x13076c
12e064 mov r0,r5
12e068 bl  0x13080c
12e06c mov r3,#1
12e070 strb r3,[r6]
```

These are **three calls on the same stack-local object**, not three independent RTE update handlers. `0x130510` initializes its fields (`+0,+4,+8,+0x18`, the last to -1) and installs an inner vtable pointer at `+8` via `0x1304ec`. `0x13080c` checks `+0x18`, optionally calls imported `0x10e2ac`, and restores the inner vtable at `+8`. It is cleanup/finalization-like; exact class identity unproven.

## Stage3 connection already present in lifecycle research

```asm
13076c push {r4,lr}
130774 bl 0x13067c
130778 cmp r0,#0
130784 bne 0x1307a8
130788 bl 0x13066c
13078c cmp r0,#0
130790 beq 0x1307d8
130794 bl 0x699594   ; GTF2 startEfsDriver()
130798 cmp r0,#0
13079c bne 0x1307b0
```

The direct `0x130794 → 0x699594` call was **already verified and documented** in `gtf2-lifecycle.md` as the delayed-HMI-start Stage3 path. The new join is the exact upstream event `eSIDThreadManRTEUpdateDone` through `0x12dfb0` and the local stack object. Therefore the correct synthesis is:

```
ThreadMan run() 0x12e380
  -> message loop 0x12e0a8
    -> processMessage 0x12dfb0
      -> eSIDThreadManRTEUpdateDone (0x2afa)
        -> 0x130510  construct temporary helper
        -> 0x13076c  conditionally run Stage3 startup path
          -> 0x13067c / 0x13066c guards
          -> 0x699594 startEfsDriver() [existing lifecycle finding]
        -> 0x13080c  finalize temporary helper
        -> mark RTE completion flag
```

## What this does not prove

- The event name does not prove that ASI RTE subscriptions have completed or identify the event producer.
- `0x13076c` does not always call `startEfsDriver()`: guard branches can bypass it.
- `0x130510` and `0x13080c` must not be described as independent IPC/RTE registration calls.
- The two ThreadMan completion flags and the separate Stage3 process-start return code should not be conflated.
- This does not supersede the other documented `startEfsDriver()` callsites `0x122eac` and `0x692f20`.

Next evidence target: producers of `0x2af9/0x2afa` and exact `0x13067c/0x13066c` DP predicates. Avoid duplicating existing `gtf2-lifecycle.md` analysis.



### Перенесено из `gtf2-threadman-completion-events.md`

# Thread-manager event names resolve callback initialization trigger

Stock `STAGE2.1/bin/gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Cross-checked against the complete 3420-line `gtf2-lifecycle.md`; these exact addresses are not already covered there. This note corrects the tentative selector interpretation in `gtf2-guarded-init-real-entry-and-caller.md`.

## Verified source-level names, not guessed transport IDs

The dispatch function **0x12dfb0** compares `r1` against `0x2af9` and `0x2afa` at `0x12dfb4` and `0x12dfd8`. Its own ARM literal loads for the two diagnostic calls identify them:

| Value | Diagnostic string VA | Exact string | Conditional action |
| --- | --- | --- | --- |
| `0x2af9` | `0x7c33d5` | `processMessage(eSIDThreadManDPInitDone)` | check flag at `r2`; `0x12df20`, `0x68f594`, set flag |
| `0x2afa` | `0x7c33fd` | `processMessage(eSIDThreadManRTEUpdateDone)` | check flag at `r3`; `0x130510`, `0x13076c`, `0x13080c`, set flag |
| other | `0x7c3428` | `processMessage(): Unexpected Message` | unexpected-message diagnostic |

Literal slots `0x12e09c`, `0x12e0a0`, `0x12e0a4` point to these strings respectively. The names are embedded diagnostics and indicate **internal ThreadMan completion events**, not external IPC method IDs. A call to `0x68f594` follows the **DPInitDone** branch, not the RTEUpdateDone branch. This does not prove what `0x68f594` registers with any external service.

## Direct upstream call chain

A complete direct ARM BL scan of the original executable PT_LOAD found:

- `0x112e18 BL 0x12e380` (one direct caller)
- `0x12e3e8 BL 0x12e0a8` (one direct caller)
- `0x12e0f8 BL 0x12dfb0` (one direct caller)

The routine `0x12e380` has its own literal diagnostic `run()` at `0x7c34bf` (literal slot `0x12e4c8`). It first calls `0x12e294`, then `0x14c348`, `0x12e124`, and the `0x12e0a8` processing loop.

At `0x12e0a8`, `0x69b29c` supplies a nonnull object, `0x14e58c` stores it in a stack-local pointer, and `0x14e59c` (a wrapper that loads the pointer and tail-branches to `0x69b45c`) produces the value passed as `r1` to `0x12dfb0`. The two byte addresses passed as `r2/r3` are local flags at `sp+7` and `sp+6`. The loop repeats until both are nonzero (`0x12e104..0x12e11c`). This proves a **two-event completion wait/dispatch** structure. Exact origin of the queue messages remains open.

The higher-level caller `0x112e18` sits in the GTF2 initialization path and passes a stack object to `run()`. Its nearby ELF diagnostic string `Starting initialization` at `0x7bd731` is referenced by the surrounding routine, but do not claim it is emitted at a particular runtime timestamp without a trace.

## Corrected interpretation

The previously observed keyed-container operations `0x12df20 -> 0x12ff70` are executed on the DP-init-complete path, followed by creation of the 52-byte callback object. The event name provides the first reliable semantic classification of the trigger; it does **not** make `0x12ff70` an IPC configuration function. `0x10eb7c` remains the already-resolved `util::SharedPtrDefaultBase` constructor.

New known chain:
```
0x112e18
  -> 0x12e380 ('run()')
    -> 0x12e0a8 (process two completion events)
      -> 0x12dfb0 ('processMessage')
        eSIDThreadManDPInitDone (0x2af9)
          -> 0x12df20 (keyed-container operations)
          -> 0x68f594 -> 0x68ee80 -> 0x69780c -> 0x6977a4
        eSIDThreadManRTEUpdateDone (0x2afa)
          -> 0x130510 -> 0x13076c -> 0x13080c
```

Next: inspect the producers of both named completion messages and the side effects of the three RTEUpdateDone calls. Distinguish *ThreadMan completion* from actual ASI IPC subscription. No implementation specification or firmware bytes committed.


## Архив остальных точных исследовательских заметок

Сохранённые исходные материалы для воспроизведения и аудита выводов.


### Перенесено из `gtf2-callback-guard-container-correction.md`

# Reassessment of guarded callback initialization: 0x12ff70 is not a proven IPC configurator

Source: stock extracted `gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This corrects the tentative wording in `gtf2-callback-owner-guarded-init.md` after inspecting the callee, not just its arguments.

## Actual function body

```asm
12ff70 ldr r0,[r0]
12ff74 cmp r0,#0
12ff78 bxeq lr
12ff7c ldr r3,[r0,#4]
12ff80 cmp r1,r3
12ff84 bge 12ff98
12ff88 ldr r0,[r0,#0x48]
12ff8c cmp r0,#0
12ff90 bne 12ff7c
12ff94 bx lr
12ff98 cmp r3,r1
12ff9c bge 12ffb0
12ffa0 ldr r0,[r0,#0x4c]
12ffa4 cmp r0,#0
12ffa8 bne 12ff7c
12ffac bx lr
12ffb0 cmp r0,#0
12ffb4 bxeq lr
12ffb8 cmp r2,#0
12ffbc add r0,r0,#8
12ffc0 bne 12ffc8
12ffc4 b 12fec8
12ffc8 mov r1,r2
12ffcc b 12fc64
```

The routine traverses a structure using `+0x48`/`+0x4c` pointers according to a comparison with the integer key at `+0x04`, then tail-calls `0x12fec8` or `0x12fc64` on a field at node `+8`. This is a **keyed tree/container lookup/update pattern**, not a demonstrated wait or IPC configuration API. The precise effects of the two tail targets remain to be established.

The preceding `0x12df20` passes keys `4,5,3` and values `0,0,0x530` respectively to this routine. Those are **container operations**, not established ASI method IDs or transport channels. In particular, `0x530` must not be promoted to an IPC channel identifier from this call alone.

## Upstream linkage limitation

A direct ARM BL scan of `0x110000..0x780000` finds **zero direct BL callers of `0x12dfb8`**. A literal 32-bit address search of the extracted ELF also finds no exact pointer to `0x12dfb8`. This is negative evidence limited to those two mechanisms; the function may be reached by a computed branch, a veneer, a register-indirect call, or other paths. No invocation count or initialization timing can be asserted.

The existing chain from `0x12e014` through `0x68f594`, `0x68ee80`, `0x69780c`, and `0x6977a4` is still valid *conditional on execution of the `0x12dfb8` branch*. `0x10eb7c` is already resolved to `util::SharedPtrDefaultBase` constructor and is not the IPC subscription.

## Integration with prior GTF2 findings

The large `gtf2-lifecycle.md` already proves a separate 180-slot DP event accumulator and a ViewManager-owned event queue. The container traversed by `0x12ff70` is **not proven identical** to either subsystem. The HMI owner singleton and the 52-byte callback-vtable object are also separate observations pending a real dataflow join.

Next inspect `0x12fec8` and `0x12fc64` to classify the container's value semantics; then trace the `0x12dfb8` entry via its actual calling convention. Avoid further 'IPC configuration' claims until ASI import or descriptor/registration code is directly linked.



### Перенесено из `gtf2-callback-object-construction.md`

# Stock ELF: callback table object construction and first caller

Source: original `STAGE2.1/bin/gtf2` (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`). This is an extension of `gtf2-callback-pointer-table.md`, based on decoding actual ARM instructions and direct BL references.

## Exact construction chain

`0x68eeb4 BL 0x69780c` in the function beginning `0x68ee80`. This is a direct call, not an inferred association from proximity.

`0x69780c`:
- `0x697814 MOV r0,#0x34`; `0x69781c BL 0x10dcac` allocates a 52-byte object (allocator behavior inferred from usage; direct call and allocation size are observed).
- `0x697820 MOV r1,r6`; `0x697824 MOV r5,r0`; `0x697828 BL 0x6977a4` initializes the allocated object using the passed argument.
- `0x69782c MOV r0,r4`; `0x697830 MOV r1,r5`; `0x697834 LDR r2,[pc,#0xc]` loads the literal `0x68dbe4` from `0x697848`; `0x697838 MOV r3,#0`; `0x69783c BL 0x10eb7c`. **Do not label this IPC registration yet**: the function might be an ownership/container assignment helper. The call and arguments are the evidence.

`0x6977a4`:
- Stores incoming `r1` at object `+0xc` and incoming `r2` at `+0x8` (instructions `0x6977b8` and `0x6977bc`).
- `0x6977cc BL 0x6998f4` and `0x6977d4 BL 0x10edb0` initialize subobjects.
- Loads `0x88e6b0` from literal `0x697800`; `0x6977e8 STR r2,[r4,#0x24]` writes a derived table pointer to object `+0x24`. `0x6977ec STR r3,[r4,#0x1c]` writes the other table pointer (derived from literal `0x88e360`) to `+0x1c`.
- `0x6977f4 BL 0x10e1a4` is another helper, not yet classified.

The earlier `0x693804` and `0x693884` functions likewise embed `0x88e6b0`, but they are **not proven to be invoked by the above construction path**. Direct BL scans find one caller of `0x6977a4` (`0x697828`), one caller of `0x69780c` (`0x68eeb4`), and no direct BL callers of `0x693804`/`0x693884` in the scanned executable range. This is consistent with other entry paths (including virtual calls), not proof of them.

## Next proof gap

At `0x68ee80` the code also calls `0x693294` at `0x68ee98` and `0x6921cc` at `0x68eea4` before constructing the object. Determine the semantic role of the caller and trace what happens to the object initialized at `0x6977a4`. A constructor storing a vtable pointer is not evidence of a live IPC subscription.

No IAA design or protocol naming is inferred here.



### Перенесено из `gtf2-callback-object-vptr-and-caller.md`

# GTF2 callback object: verified constructor ownership and vptr correction

**Source:** original `STAGE2.1/bin/gtf2` extracted again from the user-supplied Drive archive; SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. The extraction was reproduced using CIFS/IFSPTTBL, verified Adler-32 frames and system `liblzo2.so.2` decoder. ARM words below were independently read from this ELF.

## Verified direct call chain (new)

```
0x68f594 (caller function)
  0x68f59c: r0 = 4
  0x68f5a0: BL 0x10e384
  0x68f5a4: r4 = return value
  0x68f5a8: BL 0x68ecf0
  0x68f5ac: LDR r3, literal 0xdb0c9c
  0x68f5b4: STR r4, [r3]       ; global storage
  0x68f5b8: BL 0x68ee80
  0x68f5bc: BL 0x12e294

0x68ee80
  0x68ee98: BL 0x693294
  0x68eea4: BL 0x6921cc
  0x68eeb4: BL 0x69780c

0x69780c
  0x697814: MOV r0, #0x34     ; 52-byte allocation request
  0x69781c: BL 0x10dcac
  0x697828: BL 0x6977a4     ; constructor
  0x69783c: BL 0x10eb7c     ; PLT-style import trampoline, not locally implemented method
```

Direct BL scan over the ELF executable VA range found **one** caller of `0x68ee80` at `0x68f5b8`; one caller of `0x69780c` at `0x68eeb4`; one caller of `0x6977a4` at `0x697828`. The global address `0xdb0c9c` is stored immediately before the callback-object setup. This shows an initialization chain; it **does not establish live IPC registration**.

## Correction: multiple vptrs and table segments

The `0x6977a4` constructor loads the literal `0x88e6b0`, but writes **derived addresses** rather than blindly using that base as the object's vptr:

- `0x6977b4`: `ADD r2,r3,#0x278` => `0x88e928`; `0x6977bc`: `STR r2,[r4,#8]`.
- `0x6977c4`: `ADD r2,r3,#0x8` => `0x88e6b8`; `0x6977c8`: `ADD r3,r3,#0x260` => `0x88e910`; `0x6977c8`: `STM r4,{r2,r3}` => object `+0` receives `0x88e6b8`, object `+4` receives `0x88e910`.
- `0x6977d8`: loads `0x88e360`; `0x6977e8`: stores `0x88e928` at object `+0x24`; `0x6977ec`: stores `0x88e360` at object `+0x1c`.

The main 148-entry function-pointer array starts at `0x88e6b8`, and **that exact address is installed at object +0**. The adjacent secondary table starts at `0x88e910` (preceded by `0xfffffffc` and zero at `0x88e908` and `0x88e90c`). `0x88e928` is a further subtable pointer, not a synonym for `0x88e6b8`.

The 12 unresolved DP writer pointers in `gtf2-unresolved-callback-pointer-slots.csv` remain directly verified in the first array. This correction supersedes the previous document's warning that the object's vptr might equal `0x88e6b0`: **it equals `0x88e6b8` at object +0 in this constructor**.

## Imported helper, not a confirmed registration

`0x10eb7c` is one of a series of PLT-style import trampolines (ARM PC-relative branch through a table). It has **525 direct BL call sites** in the scanned executable range. Its broad use is consistent with a generic library helper, not evidence of a dedicated `IHmiKss` registration API. The exact imported symbol must be resolved through dynamic relocation metadata before assigning semantics.

The same constructor call sequence passes an object pointer as `r1`, a literal `0x68dbe4` as `r2`, and zero as `r3` into that imported helper. The return value is not used as proof of successful subscription.

## Next missing proof

1. Resolve the PLT/GOT imported symbol behind `0x10eb7c` from the stripped ELF's dynamic tables (QNX-specific layout may require program-header rather than section-header parsing).
2. Track `0x68f594` from its callers and `0xdb0c9c` global consumers.
3. Recover which dispatch path makes virtual calls through `[object + 0]` (`0x88e6b8`), and correlate with the `IHmiKss` descriptor.
4. Do not treat slot indices as wire protocol method numbers until the registration/dispatch relationship is established.

This is stock behavior research, not a design document for IAA.



### Перенесено из `gtf2-callback-owner-guarded-init.md`

# Callback-table owner: upstream guarded initialization path

Source: original stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This note extends `gtf2-callback-object-vptr-and-caller.md` and integrates the previously documented separate HMI-owner, DP-slot and ViewManager lifecycles. Direct ARM BL targets and condition branches were decoded from executable bytes, not guessed from names.

## New direct caller

The only direct ARM `BL` caller of `0x68f594` found in the scanned executable interval `0x110000..0x700000` is **`0x12e014`**, inside a function beginning at **`0x12dfb8`**.

```asm
12dff4  mov r1, #2
12dff8  ldr r2, [pc, ...]
12dffc  bl 0x10e120
12e000  ldrb r3, [r5]
12e004  cmp r3, #0
12e008  bne 0x12e090         ; skip setup when flag already nonzero
12e00c  mov r0, r4
12e010  bl 0x12df20
12e014  bl 0x68f594         ; callback-table setup chain
12e018  mov r3, #1
12e01c  strb r3, [r5]       ; set initialized flag
12e020  b 0x12e090
```

Thus the previously documented `0x68f594 -> 0x68ee80 -> 0x69780c -> 0x6977a4` path is reached **conditionally** and followed by a byte flag set to one. The guard appears to prevent repeated setup *on this branch*. It does not by itself prove a process-wide singleton or a live IPC subscription. The enclosing routine has additional branches at `0x12e024` and `0x12e03c` that initialize a different subsystem when another flag is zero.

## Additional preceding configuration

The immediately preceding call `0x12df20` (at `0x12e010`) performs configuration before constructing the callback object:

```asm
12df50  bl 0x12dcd4
12df54  mov r1,#4
12df58  mov r2,#0
12df60  bl 0x12ff70
12df68  mov r1,#5
12df6c  mov r2,#0
12df70  bl 0x12ff70
12df78  mov r1,#3
12df7c  mov r2,#0x530
12df80  bl 0x12ff70
```

These are three direct calls with arguments `(4,0)`, `(5,0)`, `(3,0x530)` and the same object-derived first argument. **Do not call them ASI subscription parameters** without resolving `0x12ff70`.

## Updated architecture boundary

The newly traced path is:
```
0x12dfb8 (conditional init, flag check)
  -> 0x12df20 (pre-configuration)
  -> 0x68f594 (global storage initialization)
      -> 0x68ee80
          -> 0x69780c
              -> 0x6977a4 (52-byte object, vptr +0 = 0x88e6b8)
              -> 0x10eb7c (imported util::SharedPtrDefaultBase ctor)
  -> set initialized flag = 1
```

This is **separate from** HMI owner lazy singleton `0x2bae28/0x25ef60`, and separate from the GTF2-local 180-slot DP notification system `0x120e94/0x122338`. No edge between those mechanisms has been established yet.

## Next proof target

Identify callers of `0x12dfb8`, resolve the owner and address of its flag byte, and inspect what `0x12ff70` configures. Resolve ASI IPC registration via imports/callers rather than mistaking the shared-pointer constructor for registration. The 148 vtable entries are not confirmed wire-method indices.

No proprietary ELF bytes or implementation design is committed.



### Перенесено из `gtf2-callback-pointer-table.md`

# New evidence: 12 unresolved DP writers appear in one stock ARM function-pointer table

Source: extracted original `STAGE2.1/bin/gtf2` (10,180,269 bytes; SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`). This investigation is distinct from the earlier nearest-prologue/name recovery: it scans **literal 32-bit references to the candidate function entrypoints** in the binary.

## Direct observations

- At VA `0x88e6b0` and `0x88e6b4`, two 32-bit words are zero. Beginning at `0x88e6b8` is a contiguous array of **148 function-like 32-bit addresses** through `0x88e904` inclusive. The next word at `0x88e908` is `0xfffffffc`, followed by zero at `0x88e90c`, consistent with a new adjacent table or secondary layout. **The function-pointer array extent is a structural hypothesis** until the ABI layout is independently verified.
- Each of the 12 previously unresolved DP write functions has an **exact pointer entry** in this array. No approximate address or string-name match is required. See `gtf2-unresolved-callback-pointer-slots.csv` for every pointer VA and index (zero-based relative to `0x88e6b8`).
- The table **base pointer `0x88e6b0`** appears as a literal at code VAs `0x693864`, `0x6938dc`, and `0x697800`. For example, ARM `LDR r3, [pc, #0x54]` at `0x693808` loads the first literal at `0x693864`, whose value is `0x88e6b0`. The surrounding code at `0x693818` and `0x693824` writes derived pointers to an object rooted at `r4` (the incoming `r0`); this is **object initialization evidence** rather than merely a detached static address table.
- The table contains many other callback-like functions, so these 12 are **not isolated unknown functions**. The slot index supplies a concrete path for the next phase: identify the interface object and its dispatch machinery.

## Important limitations

- This **does not yet prove** that the table is the primary `IHmiKss` virtual method table, nor that the slot order is the IPC wire method order. Do not name the slots or infer a protocol method number from the index.
- The ARM function entrypoints are still identified using the earlier nearest-prologue heuristic; the new contribution is their **independent literal-pointer reference**.
- The array has a pair of leading zero words, but the object's vptr is observed as `0x88e6b0`, not automatically as `0x88e6b8`. It is premature to impose an Itanium ABI `vptr + 8` convention.
- This table alone does not establish where the IPC subscription occurs, how `gss_ipc` dispatches messages, or how the DP values reach Kanzi.
- No firmware binaries or raw proprietary assets are committed.

## Follow-up target

Trace the object initialized at `0x693804` / `0x6977a4`, identify the code that receives or registers its pointer, and correlate the table with `asi.gss.ipc.rte.hmi.IHmiKss` and the `IHmiKssReply` descriptor. Only then can the slot index be interpreted as a confirmed callback mapping.



### Перенесено из `gtf2-guarded-init-real-entry-and-caller.md`

# Correction: real entry of guarded initialization is 0x12dfb0, called directly

Source: original stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

## Corrected function boundary

The previous `gtf2-callback-guard-container-correction.md` reported zero direct callers of `0x12dfb8`. That was an overly literal prologue-based scan. **The entry is `0x12dfb0`, with two instructions before the PUSH prologue**:

```asm
12dfb0  movw r12,#0x2af9
12dfb4  cmp  r1,r12
12dfb8  push {r4,r5,r6,lr}
12dfbc  mov r4,r0
12dfc0  sub sp,sp,#0x20
12dfc4  mov r5,r2
12dfc8  mov r6,r3
12dfcc  beq 12dfe4
12dfd0  movw r3,#0x2afa
12dfd4  ldr r0,[pc,#0xbc]
12dfd8  cmp r1,r3
12dfdc  bne 12e078
12dfe0  b 12e024
```

The direct caller is at **`0x12e0f8 BL 0x12dfb0`**, in function beginning `0x12e0a8`:

```asm
12e0cc bl 0x69b29c
12e0d0 subs r1,r0,#0
12e0d4 beq 12e104
12e0d8 mov r0,sp
12e0dc bl 0x14e58c
12e0e0 mov r0,sp
12e0e4 bl 0x14e59c
12e0e8 mov r2,r6
12e0ec mov r3,r5
12e0f0 mov r1,r0
12e0f4 mov r0,r7
12e0f8 bl 0x12dfb0
12e0fc mov r0,sp
12e100 bl 0x14e914
```

The callee first compares the input `r1` to **`0x2af9`** and **`0x2afa`**, then branches to two distinct initialization paths. Therefore the callback object is created only on the relevant gated branch, not unconditionally for every invocation. `0x12e0a8` also loops around `0x69b29c` until its two stack-local status bytes become nonzero; the precise semantics of these helper functions are not yet established.

**Correction to previous research:** lack of BL references to `0x12dfb8` does not mean the function is only indirectly invoked. Searching for a canonical ARM prologue alone can miss a real function entry with pre-prologue comparisons. The documented zero-caller observation is true only for the *interior address* `0x12dfb8`, not for the function.

## 0x12ff70 container semantics

The full body of `0x12ff70` was checked against original bytes. It follows keyed tree links `node+0x48` and `node+0x4c` comparing `node+4` to `r1`, then dispatches from `node+8` to `0x12fec8` when `r2=0`, or `0x12fc64` when `r2!=0`. These are not identified ASI IPC setup calls. The `0x12fec8` path includes `0x12fe04`, version/check comparisons, and a tail call to imported `0x10e264`; `0x12fc64` invokes `0x127f48`, imported `0x10eb10`/`0x10f1dc`, then `0x113f24`. Exact semantics of those imported routines require relocation lookup.

## Confirmed joined path

```
0x12e0a8 (loop, obtain/transform input via 0x69b29c, 0x14e58c, 0x14e59c)
  -> BL 0x12dfb0 (key selector 0x2af9 or 0x2afa)
     -> conditional 0x12df20 (keyed container updates)
     -> conditional 0x68f594
        -> 0x68ee80 -> 0x69780c -> 0x6977a4
           (52-byte callback object with vptr 0x88e6b8)
        -> 0x10eb7c (imported util::SharedPtrDefaultBase constructor)
```

This is **not** proof that `0x2af9`/`0x2afa` are IPC method numbers. Their role is observed as selectors in the function, but transport provenance must be established by tracing `0x14e59c` and `0x69b29c`.

This corrects the previous prologue boundary and caller-negative conclusion. Do not create an IAA implementation contract from this evidence.



### Перенесено из `gtf2-ipc-callback-read-bounds.md`

# IHmiKss callback payload read-bound audit

Derived from `docs/fpk1/gtf2-ipc-to-dp.csv`, **not** from a fresh ELF run. The underlying table's ARM provenance is checked by `export_ipc_dp_table.py` when supplied the original GTF2 binary.

## New observations

- **176 distinct DP IDs** across **34 callback labels**: 33 named callbacks and one unresolved label `unknown` containing 12 DP rows.
- All **33 named callback groups** have non-overlapping byte ranges among their exported reads. This does not prove that their payloads contain only those fields.
- The `unknown` aggregate has **5 byte-overlap occurrences**. It is **not one verified IPC callback**, and its apparent 20-byte read extent **must not be used** as a message schema.
- The largest observed named callback read extent is **22 bytes**, for `Config_Installation_Coding`. This is a *minimum readable extent*, not an asserted C struct size or wire length.
- Field offsets refer to the callback payload pointer inferred by the existing exporter; packing, endianness of the IPC transport, nested structures, and omitted fields are not established by this audit.

## Implementation consequence

For an IAA replacement, dispatch on the **real callback identity**, not solely on DP ID or the placeholder `unknown`. Each named callback can be represented by an observed sparse set of offset/width reads, but the decoder must validate incoming payload length against the highest accessed end offset and must not assume that the computed lower bound equals the full IPC message size.

The 12 unresolved rows need a **binary-backed recovery of callback function boundaries and their names** before implementing their transport decoding. Grouping them under one callback would produce ambiguous overlapping fields.

## Reproduce

```sh
python3 tools/fpk1/research/gtf2/audit_ipc_callback_layouts.py docs/fpk1/gtf2-ipc-to-dp.csv --expect-stock-count --output docs/fpk1/gtf2-ipc-callback-read-bounds.csv
```

The derived CSV is an **analysis artifact**, not a stock IPC ABI specification.



### Перенесено из `gtf2-ipc-field-name-recovery.md`

# Recovering original IHmiKss IPC field names

## Status: original field identifiers are not established

The stock GTF2 ARM ELF permits reconstruction of the following for each of **176** IPC-to-DP writes:

- IPC callback name (33 named callback types, plus an unresolved callback grouping);
- payload byte offset and load width (`u8`/`u16`);
- 32-bit DP ID and write call site.

See `docs/fpk1/gtf2-ipc-to-dp.csv` for the full evidence table. The `field_name` column is **intentionally unknown**: a load such as `ldrb r2,[rN,#4]` proves the field's position, not its C++/IDL identifier.

### Names we *can* identify, but must not confuse with IPC field names

| IPC callback | Payload offset | DP ID | Scene property | Confidence |
| --- | --- | --- | --- | --- |
| `TelltaleHMI_Display` | `+0x04` | `0x020002CD` | `ESP` | Verified handler/constructor/receiver chain |
| `TelltaleAALA_Display` | `+0x01` | `0x02000217` | `Limiter`, `Limiter_shadow`, `Cruise_shadow` | Candidate static join; not original IPC names |
| `TelltaleAALA_Display` | `+0x07` | `0x02000220` | `praediktivesACC`, `PEA_Foot`, `ACC_STA` | Candidate static join; not original IPC names |
| `ActTest_SoftLEDs` | `+0x04` | `0x0200016B` | `Limiter`, `Limiter_shadow`, `Cruise_shadow` | Candidate static join; not original IPC names |

The 176-entry source-write inventory and the scene join are different layers: one IPC field may affect multiple scene properties, and some DP IDs have no proven scene sink. Never rename an IPC field to a scene property without an IDL/schema or equivalent binary metadata tying that exact identifier to the payload offset.

### Binary/firmware evidence checked

- Stock GTF2 contains callback strings and numerous unrelated `DP_ID_...` logging strings, but no confirmed mapping from the above IPC field offsets to their original source identifiers.
- The provided `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip` includes `KSSApplication.bin` (599,924 bytes); literal searches of that file for `IHmiKss`, `TelltaleHMI_Display`, and `ESP` returned no hits. This is **not** proof the KSS firmware lacks an encoded schema.
- The provided firmware archive does not list obvious `.h` or `.idl` source files.

### Evidence required for exact names

Locate the generated `asi.gss.ipc.rte.hmi.IHmiKss` C++ headers, the IPC/RTE IDL schema, or KSS signal specification for this firmware revision. For each callback, map schema member order/offset and width to the stock ELF load instructions. Only then replace `unknown` in the canonical CSV, with a citation to the schema. Until that source is found, **the actual IPC member names remain unresolved**.

The current table does establish the exact numeric interface (callback, byte offset, type, DP ID), so replay or tracing can proceed without guessing symbolic member names.



### Перенесено из `gtf2-rte-stage3-dp-guards.md`

# Exact DataPool predicates and diagnostic outcomes in ThreadMan RTE completion Stage3 branch

Source: stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This extends the already-documented `0x130794 -> startEfsDriver()` path without duplicating the startup graph in `gtf2-lifecycle.md`.

## Exact DP comparisons

Both small GTF2 functions tail-branch to shared comparator `0x1305e4`:

```asm
13066c ldr r0,[pc,#4]     ; literal at 130678 = 0x020002bb
130670 mov r1,#0xab       ; expected byte = 171
130674 b   1305e4

13067c ldr r0,[pc,#4]     ; literal at 130688 = 0x02000236
130680 mov r1,#2         ; expected byte = 2
130684 b   1305e4
```

At `0x1305e4`, the helper builds a temporary DP value holder, calls `0x131ed4` to retrieve the DP byte, releases the holder through `0x131be8`, and returns **1 only when the read succeeds and the returned byte equals the expected value** (`0x130628–0x130638`). On read failure it logs via literal string `0x7c3aec`: `Can't read the DataPool field: %u!` and returns false. The exact field width in the original DataPool definition is not independently established; this comparator checks the retrieved byte.

## Full conditional path and original diagnostic strings

```text
eSIDThreadManRTEUpdateDone (0x2afa)
  -> 0x13076c
     -> read DP 0x02000236, compare byte 2
        if true:
          0x1307a8 -> 0x1306f0
          diagnostic 0x7c3b0f: "Delay the HMI start by %u ms."
          on timer failure 0x7c3b2d:
            "Can't start the timer! Enabling HMI immediately."
        if false:
          -> read DP 0x020002bb, compare byte 171
             if true:
               -> 0x130794 -> 0x699594 startEfsDriver()
                  on failure: 0x1307b0, diagnostic 0x7c3b5e:
                    "Problem with executing Stage 3 files. Starting immediately."
             if false:
               -> 0x1307d8, diagnostic 0x7c3b9a:
                 "Non-ECL Mode Enabled. Starting HMI immediately."
```

The diagnostics identify this as **delayed HMI startup versus immediate HMI startup / Stage3 execution selection**, not a generic ASI IPC readiness routine. The exact semantic names of DP IDs `0x02000236` and `0x020002bb` should be recovered from the existing `gtf2-ipc-to-dp.csv` and callback write provenance before assigning a source signal. The word “ECL” is a **literal stock diagnostic**, not an independently decoded enum.

### Machine-code anchors

- `0x130774 BL 0x13067c`; `0x130778 CMP r0,#0`; `0x130784 BNE 0x1307a8`.
- `0x130788 BL 0x13066c`; `0x13078c CMP r0,#0`; `0x130790 BEQ 0x1307d8`.
- `0x130794 BL 0x699594` (previously documented `startEfsDriver()`).
- `0x130798 CMP r0,#0`; `0x13079c BNE 0x1307b0` (Stage3 error path).
- `0x1307a8` tail-branches to `0x1306f0` (delay-timer path).
- `0x1307d8` logs non-ECL immediate-HMI path.

**Limits:** Static disassembly does not establish actual DP values or which branch ran on hardware. The two DP comparisons are not proof that RTE subscriptions are complete. This branch does not supersede the other Stage3 callsites `0x122eac` and `0x692f20`.

Next: resolve the two DP-ID names against the existing 176-ID callback mapping and find the producers of `eSIDThreadManDPInitDone` / `eSIDThreadManRTEUpdateDone`.



### Перенесено из `gtf2-shared-pointer-import-resolution.md`

# Resolution of imported helper at 0x10eb7c: shared-pointer ownership, not IPC registration

Original stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. ELF is section-stripped but retains PT_DYNAMIC, DT_JMPREL, DT_SYMTAB and DT_STRTAB.

## Reproducible resolution

- `0x10eb7c` contains ARM PLT stub words `e28fc609 e28cca56 e5bcfbd4`.
- Decode the rotated ARM immediates and PC-relative address calculation: `0x10eb7c + 8 + 0x900000 + 0x56000 - 0xbd4 = 0xa65758` (GOT slot).
- `DT_JMPREL=0x10c52c`, `DT_PLTRELSZ=4680`, `DT_PLTREL=REL`. The GOT slot is matched by relocation **index 425** (zero-based), whose symbol index is **560**.
- `DT_SYMTAB=0x10150c`, `DT_STRTAB=0x1044ec`, `DT_SYMENT=16`. Symbol 560 has name `_ZN4util20SharedPtrDefaultBaseC2EPvPFvS1_S1_ES1_`.
- Demangled: `util::SharedPtrDefaultBase::SharedPtrDefaultBase(void*, void (*)(void*, void*), void*)`. This is a constructor for shared-pointer ownership/control metadata, **not a dedicated IHmiKss registration API**.

## What the call actually receives

At `0x69782c–0x69783c`:
```asm
69782c  mov r0, r4            ; destination/control object (incoming to 0x69780c)
697830  mov r1, r5            ; freshly allocated/initialized 52-byte object
697834  ldr r2, [pc, #0xc]   ; literal 0x68dbe4 (deletion function candidate)
697838  mov r3, #0
69783c  bl  0x10eb7c         ; SharedPtrDefaultBase constructor
```
This explains why the object pointer and a function pointer are passed together. The function pointer at `0x68dbe4` is a **deleter candidate** according to the imported constructor's signature; its behavior still needs direct verification. The 52-byte object's own `vptr=0x88e6b8` remains independently established by `0x6977a4`.

## Integration with previous documentation

- The previous `gtf2-callback-object-construction.md` and `gtf2-callback-object-vptr-and-caller.md` explicitly left `0x10eb7c` unclassified. This finding **resolves that question** and rules out treating this call as the IPC subscription.
- `gtf2-lifecycle.md` already documents the separate 180-slot DP accumulation/flush and view-manager transition lifecycle. Do not confuse that GTF2-local DP subscription mechanism with ASI `IHmiKss` IPC subscription.
- `gtf2-stock-routing-lifecycle.md` already verifies HMI owner singleton creation and wrapper receiver binding during owner construction. The 52-byte object here is a distinct observed allocation; **no relation to the HMI owner is yet established**.
- The missing step is now to trace **where the shared-pointer control object is stored and passed** and which ASI library method registers or activates the callback implementation. Do not infer a wire method number from the 148-entry vtable.

## Minimal verification

Given a local extracted ELF `gtf2`, parse the two PT_LOAD mappings and PT_DYNAMIC tags. Decode the three ARM PLT instructions at VA `0x10eb7c`, match the resulting GOT VA `0xa65758` against 8-byte REL entries in `DT_JMPREL`, and read symbol 560 via `DT_SYMTAB` and `DT_STRTAB`. No proprietary binary is committed.



### Перенесено из `gtf2-threadman-channel-index-proof.md`

# ThreadMan RTEUpdateDone producer and consumer select the same internal channel index 3

Binary: stock `gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This resolves the channel-index ambiguity left in `gtf2-threadman-message-send-receive.md`. It does **not** resolve the unrelated external `IHmiKss` method number.

## End-to-end register/field proof

The RTE callback at vtable slot 136, `0x693ff0`, sets `r1=3` and `r2=0x2afa` before `0x12ca9c`:

```asm
693ff4 movw r2,#0x2afa
693ff8 mov  r1,#3
693ffc mov  r0,sp
694000 bl   0x12ca9c
```

`0x12ca9c` forwards the channel index in `r0` and selector in `r1` to `0x69b6b8` (`0x12caa8..0x12cab8`). In `0x69b6b8`, `r6` holds that channel index and `r5` holds the selector. The message initializer `0x6abce8` is called with `r3=r6` and fifth stack argument `r5`. Its instructions **`0x6abcfc STR r3,[r0]`** and **`0x6abd00 MOV r1,lr`** establish the channel index in message field `+0` and selector in the message construction path. It also stores payload pointer at `+4`, capacity at `+8`, length at `+0xa`, and active flag at `+0xd`.

Sender `0x69b4ac`:
```asm
69b4b8 bl 0x68d7f8      ; initialize shared channel array if needed
69b4bc ldr r1,[r4]      ; r1 = message.channel_index = 3
69b4c0 bl 0x68d570      ; descriptor = table[r1]
69b4c4 ldrh r2,[r4,#10] ; message length
69b4c8 ldr r1,[r4,#4]   ; message payload
69b4d0 bl 0x68d060      ; send-side transport helper
```

The shared accessor `0x68d570` is exactly `LDR r0,[r0,r1,LSL #2]; BX lr`. The singleton accessor `0x68d7f8` returns a pointer to the shared array at `0xdb0bf4` (literal `0x68d848`), initializing it through `0x68d5b0` once.

Receiver `0x12e0a8`:
```asm
12e108 mov r0,#3
12e110 beq 0x12e0cc
12e11c beq 0x12e0cc
12e0cc bl 0x69b29c
```
At `0x69b29c`, `r4=r0` saves **3**; it calls the **same** `0x68d7f8` and passes `r1=r4` to the **same** `0x68d570` at `0x69b2ac..0x69b2b0`. Thus both sides select **table[3]**, with the same singleton array and accessor, before send/receive helper calls. The receiver subsequently uses `0x68cf00` with a 64-byte destination buffer.

This proves **same internal channel-table index and shared descriptor slot**, stronger than the earlier observation of shared helper names. It does not prove that an individual message was successfully delivered at runtime, or whether send/receive use the same underlying OS descriptor integer rather than distinct endpoints within that slot; inspect `0x68d5b0` and the channel descriptors for that detail.

## Scope / nonclaims

- Index **3** is an **internal message-channel selector**, not the external `IHmiKss` method ID and not callback slot 136.
- `0x2afa` is the **ThreadMan message selector**, not a channel number.
- Callback table slot **136** identifies the local implementation `0x693ff0`, not a wire protocol method ID.
- No runtime delivery or external ASI registration sequence is inferred from static code.

## Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x693ff0 --stop 0x69401c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b6b8 --stop 0x69b6f0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6abce8 --stop 0x6abd24
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b4ac --stop 0x69b4d8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b29c --stop 0x69b2c0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d7f8 --stop 0x68d850
```



### Перенесено из `gtf2-threadman-message-send-receive.md`

# ThreadMan completion message transport: concrete send/receive bridge

Stock GTF2 ELF SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Extends `gtf2-rte-completion-callback-slot.md`; avoids repeating the already-established callback object, DP routing and Stage3 paths.

## Sender-side verified ARM calls

`0x693ff0` is callback table entry 136 at `0x88e8d8`, not an external IPC method number. It constructs selector `0x2afa` and invokes `0x12c994`. The exact implementation:

- `0x12c994`: reads message wrapper's active byte at `+4`; only when set, loads its pointer at `+0` and calls `0x69b4ac` (`0x12c9a8..0x12c9ac`). If send returns zero, executes error reporting via `0x10e714`; updates wrapper active byte based on result (`0x12c9d4..0x12c9e4`).
- `0x69b4ac`: checks message pointer nonnull; `0x69b4b8 BL 0x68d7f8`, `0x69b4c0 BL 0x68d570`; reads **message+0x0a as a 16-bit unsigned field** and message+4 as a pointer; passes them to `0x68d060` (`0x69b4c4..0x69b4d0`). Tests result against -1 and returns boolean success/failure (`0x69b4d4..0x69b534`).
- `0x12c9fc`: calls `0x69b280` on the wrapper's owned message pointer, then clears the pointer and active byte.

These are concrete send-side edges; exact wire layout remains unproven until `0x68d060` and the underlying QNX messaging import are resolved.

## Receiver-side verified ARM calls

`ThreadMan::run` `0x12e380` invokes the processing loop `0x12e0a8`, whose `0x12e0cc` calls `0x69b29c`. In `0x69b29c`:

- `0x69b2a8 BL 0x68d7f8`, `0x69b2b0 BL 0x68d570`: same pair as sender.
- `0x69b2bc BL 0x6abf20`: acquire message object; return null is a distinct error path.
- `0x69b2f8 BL 0x68cd70`, `0x69b348 BL 0x68ce1c`: receive/prepare operations, with error checking against -1.
- `0x69b35c BL 0x68cf00`: reads into the **message object +0x10** buffer with **r2=64** and r3=0. This establishes a fixed 64-byte receive-buffer bound for this call, not the length of every possible message.
- Successful loop then obtains selector from the returned object via `0x14e58c` / `0x14e59c` and invokes `0x12dfb0`.

This establishes a common application-owned messaging helper family on both sides. It does **not** yet prove the two calls refer to the same concrete endpoint/connection ID, or that the message is carried via ASI external IPC rather than an internal QNX message channel. The consumer is the internal ThreadMan selector dispatcher, not the external RTE callback table.

## Important semantic distinction

```
External RTE callback dispatch (method number still unknown)
    -> callback vtable slot 136 / 0x693ff0
    -> 0x12c994 -> 0x69b4ac -> 0x68d060 [send-side helper]
    ... transport/channel identity not yet resolved ...
ThreadMan run / 0x12e0a8
    -> 0x69b29c -> 0x68cf00 [64-byte receive buffer]
    -> 0x12dfb0 / 0x2afa
    -> delayed/Stage3/immediate HMI startup choice
```

A slot number in a C++ vtable is not an IPC method ID. No interface descriptor → slot 136 method-name correspondence is established yet. Further work should resolve the channel or connection IDs and callback descriptor rather than infer a method name from neighboring entries.

## Reproduction

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12c994 --stop 0x12ca20
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b29c --stop 0x69b438
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b4ac --stop 0x69b550
```



### Перенесено из `gtf2-threadman-named-message-box.md`

# ThreadMan message channel resolved to named /eMsgBoxIDThreadManager

Stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This consolidates the message transport reconstruction across `gtf2-threadman-channel-index-proof.md`, `gtf2-threadman-message-send-receive.md`, and `gtf2-rte-completion-callback-slot.md`. **New evidence:** names, descriptor initialization, index-to-name mapping, and implementation characteristics of the message-box mechanism.

## Four named message boxes, initialized in exact index order

The singleton initializer `0x68d7f8` calls `0x68d5b0` with the four-word array at `0xdb0bf4`. In `0x68d5b0`, four sequential calls to `0x68d308` store returned descriptors at `[r4+0]`, `[r4+4]`, `[r4+8]`, `[r4+12]`. Their name pointers are literal loads immediately before the calls.

| Index | Descriptor store | Name pointer literal | String VA | Exact stock name | Creation call |
|---|---|---|---|---|---|
| 0 | `0x68d5f0 STR r0,[r4]` | `0x68d7c4` | `0x88cdbd` | `/eMsgBoxIDGui` | `0x68d5e8 BL 0x68d308` |
| 1 | `0x68d670 STR r0,[r4,#4]` | `0x68d7e0` | `0x88ce6a` | `/eMsgBoxIDDatapool` | `0x68d668 BL 0x68d308` |
| 2 | `0x68d6f0 STR r0,[r4,#8]` | `0x68d7e8` | `0x88cea6` | `/eMsgBoxIDApplication` | `0x68d6e8 BL 0x68d308` |
| 3 | `0x68d770 STR r0,[r4,#12]` | `0x68d7f0` | `0x88ceee` | **`/eMsgBoxIDThreadManager`** | `0x68d768 BL 0x68d308` |

All four calls use `r1=0x102` and `r2=0x1ff` (ARM MOVW opcodes), with a temporary attribute block setting max message count 64 and message size 64 for index 0, and message count 16 / size 64 for indices 1–3. These values are initializer arguments, not observed runtime queue depth.

Each failure branch logs an explicit stock string, respectively `Failure in creating message queue for HMI`, `... for DP`, `... for Application`, `... for Thread Manager`.

## Transport proof: same *named* channel, not merely similar helpers

```text
IHmiKss callback table slot 136 -> 0x693ff0
  -> message constructor (channel_index = 3, selector = 0x2afa)
  -> 0x12c994 -> 0x69b4ac
  -> 0x68d7f8 (singleton) -> 0x68d570(table,3)
  -> table[3] == descriptor created for /eMsgBoxIDThreadManager
  -> 0x68d060 (send helper)

ThreadMan run 0x12e380 -> 0x12e0a8 (r0=3)
  -> 0x69b29c
  -> 0x68d7f8 (same singleton) -> 0x68d570(table,3)
  -> table[3] == descriptor created for /eMsgBoxIDThreadManager
  -> 0x68cf00 (receive helper, 64-byte buffer)
  -> selector 0x2afa -> 0x12dfb0
  -> 0x13076c -> DP guards -> conditional Stage3/HMI startup
```

This is a **complete static join at the same named message-box descriptor**. The actual runtime scheduling, success/failure, and external `IHmiKss` wire method remain unproven.

## Implementation detail and caution about POSIX interpretation

The name strings have a POSIX-like leading slash, and stock error text uses “message queue” and references `mq_overview`. But `0x68d308` is a substantial application-level helper: it checks `strlen`, loops over eight named slots using `strcmp`, allocates and initializes internal state, and calls `pthread_cond_init` via PLT `0x10dad8`. `0x68d060` likewise contains custom allocation and shared-state checks. **Do not assert these are OS `mq_open` descriptors solely from the names**. Resolve the underlying helper implementation and imports before assigning an OS transport type.

The fourth channel is unequivocally named `/eMsgBoxIDThreadManager`; the three others are separate internal message boxes and must not be conflated with ASI `IHmiKss` interface names.

## Reproduction on original ELF

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d5b0 --stop 0x68d7f8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d7f8 --stop 0x68d850
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d308 --stop 0x68d4c4
```

Extract literal values from original executable PT_LOAD with `struct.unpack_from('<I', blob, va - 0x100000)`; decode strings at the four virtual addresses above. The executable image contains original program bytes and no synthetic instructions.

## Remaining external boundary

The internal completion-event path is statically closed up to named channel and event dispatcher. Next high-value task is the **external `IHmiKss` descriptor/method mapping for vtable slot 136**. The vtable index, ThreadMan selector `0x2afa`, and message-box index 3 are three different number spaces; none is an ASI method number.



### Перенесено из `gtf2-threadman-producers-and-startup-dp-writers.md`

# Proven producers of ThreadMan completion events and two missing startup DataPool writers

Original stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Reconciled with `gtf2-lifecycle.md` and `gtf2-ipc-to-dp.csv`: neither `0x02000236` nor `0x020002bb` appears in the 176-row CSV, which is a **restricted direct-writer inventory**, not a complete DataPool inventory.

## Completion message construction sites

A whole-executable scan for ARM MOVW immediates `0x2af9` and `0x2afa` found exactly these instruction addresses:

| Selector | MOVW instruction VA | Role |
|---|---|---|
| `0x2af9` | `0x114808` | Producer of `eSIDThreadManDPInitDone` |
| `0x2af9` | `0x12dfb0` | Consumer comparison |
| `0x2afa` | `0x693ff4` | Producer of `eSIDThreadManRTEUpdateDone` |
| `0x2afa` | `0x12dfd0` | Consumer comparison |

At `0x1147f8–0x114818`, the initialization routine invokes `0x69e2d4`, constructs the `0x2af9` message using `0x12ca9c`, then calls `0x12c994`. At `0x693ff0–0x694018`, a separate function constructs `0x2afa` through `0x12ca9c`, invokes `0x12c994`, then calls `0x12c9fc` for local cleanup. The latter helper calls `0x69b280` on the message's owned object. Both producers use the same message helper family; the consumer is `0x12dfb0` through `0x12e0a8`.

Do not equate `0x12c994` with confirmed queue insertion without following its callee `0x69b4ac` and the queue storage. Do not assume that `0x693ff0` has a direct BL caller: direct-BL census found **zero**. The function can be invoked via a vtable or callback pointer; that upstream edge remains to be resolved.

## Previously missed startup DP writer #1: 0x02000236

The original ELF contains two literal occurrences of `0x02000236`: `0x130688` (reader/guard) and `0x69436c` (writer). The latter is referenced by the function beginning at `0x694358`:

```asm
694358 ldr r3,[r1,#4]
69435c add r0,r0,#0x10
694360 ldr r1,[pc,#4]   ; [0x69436c] = 0x02000236
694364 ldrb r2,[r3,#3]  ; payload byte +3
694368 b 0x131390      ; DP setter, tail branch
```

The prior 176-DP inventory deliberately recognizes direct BL-to-setter patterns. This writer uses a **tail branch** and was therefore not represented in the CSV. The callback's source-level name is **not yet proven**; do not invent it from neighboring vtable entries.

## Previously missed startup DP writer #2: 0x020002bb

The original ELF contains two literal occurrences of `0x020002bb`: `0x130678` (reader/guard) and `0x693fec` (writer). Function `0x693fdc` writes a **fixed byte value** through a different DP helper:

```asm
693fdc add r0,r0,#0x10
693fe0 ldr r1,[pc,#4]  ; [0x693fec] = 0x020002bb
693fe4 mov r2,#171
693fe8 b 0x13143c
```

The fact that this DP is written to the value the Stage3 guard expects does **not** prove it has that value at the time of the guard read. Establish invocation order, conditional execution, and potential other writers before claiming that the Stage3 branch is always selected.

## Reconciled control-flow picture

```text
GTF2 initialization routine
  -> 0x114808 MOVW 0x2af9 -> 0x12ca9c -> 0x12c994
  -> ThreadMan processing loop 0x12e0a8
    -> 0x12dfb0 DPInitDone
      -> keyed-container operations and callback object setup

Separate GTF2 function 0x693ff0
  -> 0x693ff4 MOVW 0x2afa -> 0x12ca9c -> 0x12c994
  -> ThreadMan processing loop 0x12e0a8
    -> 0x12dfb0 RTEUpdateDone
      -> 0x13076c
        if DP 0x02000236 == 2: delayed HMI start
        else if DP 0x020002bb == 171: startEfsDriver()
        else: immediate HMI start
```

The source-level name of `0x693ff0`, its indirect callback/vtable registration, the transport between the producers and the queue consumer, and the real-time order of both messages are not yet established. This note records **binary-verified producer sites and DP writers**, not a complete IPC transport reconstruction.

## Reproduction

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x1147f8 --stop 0x11482c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x693fdc --stop 0x69401c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x694340 --stop 0x694370
```

Next: identify indirect pointer slot(s) to `0x693ff0` and `0x694358`; trace `0x69b4ac` and `0x69b29c` as the producer/consumer message bridge; then resolve callback names with direct vtable provenance.



### Перенесено из `gtf2-unresolved-callback-elf-findings.md`

# Binary-backed triage of the 12 unresolved IHmiKss source rows

**Source:** `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip` from the supplied Drive file; extracted `STAGE2.1/bin/gtf2`, 10,180,269 bytes, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

## New ELF run

The archive was decoded using the existing repository's documented CIFS/IFSPTTBL + Adler-32-checked LZO Stage2 reconstruction profile (the extracted ELF hash matches prior research). The 12 DP write addresses previously labeled `unknown` in `gtf2-ipc-to-dp.csv` were individually located in the **actual ELF**, and assigned candidate function starts by nearest preceding ARM `STMDB sp!,{...,lr}` prologue, with the next such prologue used as an upper bound.

**Result:** 12 DP writes have **12 distinct candidate function starts**. Therefore the 12 rows are **not one verified callback structure**. This is a candidate function-level split, not yet proof of 12 independent registered IPC methods; thunks and inlining require further examination.

New evidence from PC-relative literal references within the candidate function ranges:

- DP `0x0200016a`, write `0x694308`, candidate start `0x6942f0`: diagnostic `AAG_Blinker_H_aktiv (s_AB): %d` referenced at `0x694324` (string VA `0x88eef6`).
- DP `0x02000222`, write `0x694460`, candidate start `0x694448`: diagnostic `rightHandDrive: %d` referenced at `0x69447c` (string VA `0x88ef15`).
- No other printable diagnostic strings were found by this literal-pointer scan inside the ten remaining candidate function ranges. **Absence of such a string does not mean the callback has no symbolic identity.**

The complete 12-row ledger is `docs/fpk1/gtf2-unresolved-callback-functions.csv`. These diagnostic phrases are **behavioral clues**, not confirmed IPC method names or field names.

## Non-duplication check

Earlier `group_rte_dp_callbacks.py` and `name_rte_dp_callbacks.py` already grouped direct DP writes and searched `batchLock()` diagnostic names. The incremental result here is a **fresh execution against the user-supplied original ELF**, the exact 12 unresolved DP site split, and the two diagnostic-string xrefs. The canonical 176-row table is unchanged pending proof of actual callback identity.

## Next evidence needed

Resolve the 12 candidate callback entrypoints to their **registered virtual interface/vtable slots** or IPC interface descriptors; independently verify that the DP write is reached from that entrypoint. Search for call-site-to-method correspondence, not merely nearby printable strings. Then trace subscription and dispatch to distinguish an IPC callback from a helper or forwarding thunk.



### Перенесено из `gtf2-unresolved-callback-triage.md`

# Unresolved IHmiKss callback identities: non-duplicate investigation plan

## Prior work checked before adding this tool

| Existing work | Already established | Not repeated here |
| --- | --- | --- |
| `scan_rte_dp_writes.py` | Direct `BL 0x131390`, literal DP and payload load scanner | No new DP discovery claim |
| `group_rte_dp_callbacks.py` | Nearest preceding ARM `STMDB sp!,{...,lr}` candidate function grouping | No claim to discover grouping |
| `name_rte_dp_callbacks.py` | `batchLock() failed` callback name search in a restricted diagnostic address range | No claim that diagnostic naming is new |
| `export_ipc_dp_table.py` | 176-row canonical source CSV, including 12 `unknown` entries | Canonical CSV unchanged |
| `audit_ipc_callback_layouts.py` | Offset overlap and minimum read extent by callback label | Not a callback identity resolver |

## Incremental contribution

`triage_unresolved_callback_functions.py` is a **function-level evidence ledger**:

1. Groups scanner write sites by candidate ARM function start and emits **start/end VAs** and every DP write VA per group.
2. Searches PC-relative literal pointers for printable NUL-terminated diagnostics **across the available image**, rather than requiring the pointer to lie in `0x88e000–0x88f800`.
3. Preserves the diagnostic source instruction VA, target string VA and string text for review.
4. Reports `unique-diagnostic`, `conflicting-diagnostics`, or `no-name-diagnostic` instead of silently choosing one name.
5. Never edits `gtf2-ipc-to-dp.csv` or claims an original IPC field identifier.

### Reproduce on original stock ELF

```sh
python3 tools/fpk1/research/gtf2/triage_unresolved_callback_functions.py \
  /path/to/STAGE2.1/bin/gtf2 --expect-stock-count \
  --output /tmp/gtf2-callback-function-evidence.csv
```

Compare `dp_ids` in this output to the 12 `unknown` rows in `docs/fpk1/gtf2-ipc-to-dp.csv`. The expected result is a **review queue**, not an automatically trusted rename. A `unique-diagnostic` label still needs confirmation that the string is from the actual callback function and not a nested helper or unrelated literal.

### Open issues and false-positive controls

- The nearest-prologue grouping remains **heuristic**. Nonstandard prologues, inlined code and compiler-generated thunks may cause incorrect boundaries.
- A string pointer inside a function is evidence of a reference, not proof the diagnostic executes along the DP write path.
- Printable diagnostic strings may include unrelated code messages; only the exact `Name(): batchLock() failed` signature becomes a candidate callback name.
- The tool's candidate end bound is the next matching prologue or 0x800 bytes, whichever comes first; it is **not** a verified function size.
- Payload layout and actual wire message length remain unknown.

## Evidence status

This change was reviewed against the existing repository scripts and CSV. **The new triage tool has not been run on the stock GTF2 ELF in this change.** Consequently, it reports no new recovered callback names or additional confirmed DP mappings yet.


## Первый проход по внешнему IPC и наличию библиотек (2026-10-28)

**Проверен исходный пользовательский update ZIP**, а не только извлечённый `gtf2`. В архиве 66 записей; прошивка поставляется как HSP-обёрнутые образы `stage1_ifs.img`, `stage2_ifs.img`, `stage3.img`, `app.img` и др. **Отдельных `libcomm.so` или `libasi*.so` в ZIP нет.** Поэтому следующий этап — извлечение реального ELF библиотеки из imagefs, а не поиск файла в корне ZIP.

В оригинальном `stage2_ifs.img` (23,056,578 байт) последовательность `libcomm.so` найдена по файловым смещениям `0x946a82` и `0x99b17d`, обе рядом с импортированными C++-символами `comm` внутри ELF-данных. **Это строки DT_NEEDED/символов потребителя, не доказательство наличия самостоятельного ELF `libcomm.so` по этим смещениям.** Строка `IHmiKss` также найдена в другом участке `stage2_ifs.img` по смещению `0x1fee6a`. Нельзя принимать простое совпадение строк за библиотеку-диспетчер.

**Независимый признак направления RPC в самом `gtf2`:** стоковые строки `IHmiKssProxy::HMI_ZPM_Audio_SDSstate()`, `IHmiKssProxy::Kombi_HUD_01()`, `IHmiKssProxy::HMI_Ready`, `IHmiKssProxy::HMI_ZPM_Ready`, `calling IHmiKssProxy::HMI_ZPM_BcmeLivetips(%d)` и `sendKssPopUpShown ... calling IHmiKssProxy::HMI_PopUpShown` описывают исходящие обращения к KSS proxy. Отдельные строки `HmiCommKssReplyImpl rteNoInit %d`, `rteTimeout %d` и `lost server connection, reactivating...` описывают reply/lifecycle-обработчик. Это **сильное основание разделить исходящий IHmiKssProxy и входящий IHmiKssReply**, но направление каждого метода следует доказать call graph и интерфейсными дескрипторами. В частности, не назначать слот 136 входящему wire method только по его наличию в vtable.

**Следующая техническая задача:** использовать уже имеющиеся QNX imagefs/ZV-LZF извлекатели из `tools/fpk1` и `tools/mhi2`, построить манифест `libcomm.so`/ASI/IPC ELF и только затем исследовать их экспортированный dispatch и wire формат. Это блокирует прежнюю стратегию бесконечного анализа адресов одного `gtf2`.


### Stage3 QNX6 filesystem: actual directory traversal (2026-10-28)

Вместо поиска строк в упакованном ZIP выполнена **проверка декодированного Stage3 QNX6 тома**: `stage3.img`, SignInfo flashdata offset 186, zlib 7 335 155 → 209 715 200 байт, superblock at `0x2000`, block data base `0x3000`, block size 1024. Обход выполнен через root inode, inode pointers и 32-байтные directory entries по профилю `tools/fpk1/probe_qnx6_root.py`. Посещено **268 inode**, из них **238 обычных файлов**. Проверены имена с `comm`, `ipc`, `asi`, `rte`, `hmi`, `kss`: среди распознанных коротких имён есть `/bin/gssipc-kbd` (скрипт) и `/bin/app/gssipc-kbd` (ARM ELF, 191 340 байт), но **нет `libcomm.so` и отдельной библиотеки ASI**.

**Ограничение:** этот быстрый обход декодирует только inline-имена длиной до 27 байт; QNX6 long-name reference entries пропущены. Следовательно, корректный вывод: `libcomm.so` **не найден среди распознанных файлов Stage3**, а не «библиотека отсутствует во всей прошивке». Дальше проверять Stage2 imagefs, Stage1 imagefs и длинные имена Stage3, используя существующие валидаторы. Доказательств формата wire method всё ещё нет.


### ARM32 RPC jump-table evidence (2026-10-28)

Local analysis of the original `lib/factories/libgssIpcRteHmiProxy.so` (ELF32 ARM, 348160 bytes) recovered four computed-branch dispatchers. At `0x1ac14`, the selector is transformed by `SUB r1,r1,#69`, compared to 106, then dispatched via `ADDLS pc,pc,r1,LSL#2` at `0x1ac34`; 40 of the 107 table entries target non-default handlers, corresponding to original IDs 69..175. At `0x1c458`, the selector is compared to 106 and dispatched at `0x1c45c`; 40 entries are non-default for local indices 0..106. At `0x3d77c` and `0x40c9c`, selector values 0..179 are dispatched by jump tables at `0x3d798` and `0x40ca0`; each table has 140 non-default handlers and 40 default entries. The 40 IDs in the shifted `0x1ac14` table are precisely the 40 default IDs in both 180-entry tables. This partitions IDs 0..179 into complementary sets of 40 and 140. The 0..106 table has the same 40-entry shape in local index space (shifted by 69). These are *static branch targets*, not yet confirmed external wire IDs or method names; further call-graph analysis is required to assign request/reply direction. Disassembly reproducible with `llvm-objdump -d` and reading ARM B-immediate targets from the ELF's RX segment. No firmware binaries are committed.


### Exact dispatch selector partition (2026-10-28)

Direct decoding of ARM `B` immediates in original `libgssIpcRteHmiProxy.so` (RX segment has `p_offset=0`, `p_vaddr=0`) confirms four tables: `0x1ac3c` (107 entries, selector minus 69), `0x1c464` (107 entries, selector minus 69 at `0x1c42c`), `0x3d7a0` (180 entries) and `0x40ca8` (180 entries). Default branch destinations are respectively `0x1b264`, `0x1faf4`, `0x3fe38` and `0x500f8`. The first two tables share **exactly** 40 non-default original selector IDs: `69-81, 84, 85, 87, 91, 93-108, 119, 120, 142, 172-175`. The last two share exactly the **complementary 140** non-default IDs from `0-179`. No overlap; union contains all 180 IDs. Crucial correction: `0x1c458` compares a *shifted* index (`r0 = r8 - 69` at `0x1c42c`), not independent external IDs 0-106. These numbers are proven dispatch selectors; their wire representation and method names still require tracing the call sites. Reproduction: read 32-bit little-endian branch words at each table entry, sign-extend low 24-bit displacement, compute destination = entry address + 8 + displacement*4, and compare to the respective default branch target.


### Selector 136: distinguish wire ID from callback vtable slot (2026-10-28)

The original ARM32 RPC factory ELF provides a concrete counterexample to equating a method selector with a callback vtable index. For selector **136**, the 180-entry dispatch table at `0x3d7a0` branches from entry `0x3d9c0` to handler `0x3e994`. This handler writes literal `136` to a 16-bit stack field (`MOV r3,#136` at `0x3e9a8`, `STRH r3,[sp,#168]` at `0x3e9ac`) and calls a serialization/helper routine via PLT at `0x3e9c0`. The companion table at `0x40ca8` branches from entry `0x40ec8` to `0x46a4c`; its handler loads a callback object from `[r5,#0x18]`, then performs a virtual dispatch through `[vptr + 0x18]` at `0x46a9c..0x46aa4` (vtable **slot 6**, not slot 136). These are exact code observations. It remains to establish whether this callback object is the GTF2 `HmiCommKssReplyImpl` instance, and which interface method selector 136 names. The previously known GTF2 primary-vtable slot 136 -> `0x693ff0` -> local `RTEUpdateDone` must NOT be identified with RPC selector 136 merely because the numbers match. This is now reinforced by the concrete virtual call offset in the factory library.


### Cross-check selector 136 against the stock GTF2 primary vtable (2026-10-28)

Rechecked actual ELF bytes rather than inferring callback identity. The primary GTF2 callback vtable starts at `0x88e6b8`: slot 6 (`+0x18`) points to `0x6975f4`; slot 136 (`+0x220`) points to `0x693ff0`. The factory RPC handler for selector 136 at `0x46a4c` loads an object from `[r5,#0x18]` at `0x46a8c`, then invokes `[vptr,#0x18]` at `0x46a9c..0x46aa4`. **If** this pointer is the primary GTF2 callback object, the called method is `0x6975f4`, not `0x693ff0`. The GTF2 function `0x6975f4` forwards its argument through `0x151558`, `0x14eb5c`, then tail-calls `0x162744`; unlike `0x693ff0`, it does not directly enqueue local ThreadMan selector `0x2afa`. The exact dynamic identity of `[r5,#0x18]` remains to be established; do not claim selector 136 is the wire trigger for `RTEUpdateDone`. Confirmed separate facts: factory serializer handler `0x3e994` embeds literal 136 into a 16-bit field; the receiver dispatches selector 136 through a callback virtual slot 6. The remaining task is to trace the factory's callback pointer installation and find which *actual selector* dispatches to GTF2 slot 136.


### RPC selector 177 reaches callback vtable slot 136 (2026-10-28)

New concrete mapping from original `libgssIpcRteHmiProxy.so`: the 180-entry table at `0x40ca8` selects **ID 177** through table entry `0x40f6c` (177*4) to handler `0x4fd34`. The handler performs two lookup/response steps; the second (`0x4fd94..0x4fdf0`) branches on null at `0x4fdcc..0x4fdd0`. On the null path at `0x4fdf4`, it loads `[r5,#4]` as the callback object, then `[vptr,#0x220]` and invokes it at `0x4fe04`: **vtable slot 136**. This establishes a static, conditional path **selector 177 -> vtable slot 136**, not selector 136 -> slot 136. In the GTF2 primary callback vtable, slot 136 resolves to `0x693ff0`, which enqueues ThreadMan `eSIDThreadManRTEUpdateDone` (`0x2afa`) on local channel 3. The remaining identity assumption is that `[r5,#4]` in the factory's dispatch object is indeed the registered GTF2 primary callback object; this must be checked through construction/registration before calling the full cross-library chain proven. Contrast selector 136: handler `0x46a4c` invokes slot 6 from `[r5,#0x18]`, a distinct callback field. No packet format is inferred from this evidence.


### Selector 177 callback path: corrected branch semantics (2026-10-28)

Re-disassembled stock `libgssIpcRteHmiProxy.so` at `0x40b80..0x40ca0` and `0x4fd34..0x4fe08`. Dispatcher function `0x40b80` saves its first argument in `r5` at `0x40bc0`; `r5` is therefore the dispatcher object, not a scratch pointer. Selector 177 enters `0x4fd34`. Its first lookup (`0x4fd54..0x4fd90`) conditionally calls a returned object's vtable slot 7; its second lookup (`0x4fdb4..0x4fdf0`) also conditionally calls vtable slot 7, passing literal `178` as an argument (`0x4fde4`). Both paths through the second lookup **converge at `0x4fdf4`**: `BEQ 0x4fdf4` at `0x4fdd0`, or fall-through after `BLX r4` at `0x4fdf0`. At `0x4fdf4..0x4fe04` the code loads the dispatcher object's `[r5,#4]` callback pointer and invokes its vtable slot 136 (`[vptr,#0x220]`). Thus the slot-136 call is **not conditional on a missing lookup**, correcting the previous characterization. It remains conditional on reaching this handler without exception or nonreturning helper. If `[r5,#4]` holds the stock GTF2 primary callback object, the target is `0x693ff0`, which queues local `RTEUpdateDone` (`0x2afa`). This identity is still unproven until the object's constructor/registration write to offset +4 is traced. Note that literal 178 in the second lookup is a separate observed value and should not be silently substituted for the incoming selector 177.


### Proven setter for the RPC callback field at +4 (2026-10-28)

Inspected original ARM32 `libgssIpcRteHmiProxy.so` bytes and its in-image vtable entries. The receiver-side vtable at `0x52d70` begins with function pointers `0x3d47c`, `0x40b80`, `0x3d77c`, `0x3d484`, `0x3ff98`, `0x3fe94`. The **first virtual function** `0x3d47c` is exactly `STR r1,[r0,#4]; BX lr` (ARM instructions `e5801004`, `e12fff1e`): it installs the callback pointer passed as the second argument into the receiver object's offset `+4`. The **second virtual function** is the dispatcher `0x40b80`; it preserves `this` in `r5` at `0x40bc0`. Selector 177 within this same dispatcher reaches `0x4fdf4`, reads `[r5,#4]`, and invokes `[callback_vptr,#0x220]` (slot 136) at `0x4fe04`. This now proves the internal receiver chain: **virtual slot 0 installs callback -> virtual slot 1 dispatches -> selector 177 -> stored callback slot 136**. The identity of the pointer supplied to the setter by the external `comm` registration code still needs confirmation to prove that it is the `gtf2` primary callback vtable at `0x88e6b8`. A second, distinct RPC vtable at `0x51cf8` starts with analogous setter `0x1a134` (`STR r1,[r0,#4]`), dispatcher `0x1c34c`, and 40-selector table `0x1ac14`. Do not conflate the two objects. All addresses are ELF virtual addresses in the original factory library, not GTF2 addresses. Repro: inspect 32-bit little-endian words at offsets `0x52d70` and `0x51cf8` and disassemble the listed functions.


### GTF2 passes the primary callback to its comm proxy wrapper (2026-10-28)

Direct ARM32 argument-register trace closes one more part of the registration path. At `gtf2:0x697ef4`, `MOV r2,r4` passes the original GTF2 callback object (`r4`, saved from the function's `r0` at `0x697ea4`) as **third argument** to `gtf2:0x6939b4`, called at `0x697f1c`. The fifth argument is `r4+4` (`ADD r12,r4,#4` at `0x697f0c`; `STR r12,[sp]` at `0x697f10`), matching the separate lifecycle-listener subobject. In `gtf2:0x6939b4`, third argument `r2` is preserved to `[sp,#0x24]` at `0x6939e4`, reloaded at `0x693c44`, and written to the newly allocated proxy-wrapper object's `[r5,#0x48]` at `0x693c50`. This **proves that GTF2 stores the same primary callback pointer** in its local proxy wrapper and passes its `+4` lifecycle subobject separately to the `comm::Proxy` constructor (`0x693cd0`). It does **not yet prove** that the external factory's setter at `0x3d47c` receives this pointer: the consumer of wrapper field `+0x48` and the factory-binding registration call remain to be traced. The earlier intra-factory path (setter `0x3d47c` -> `[factory+4]` -> selector 177 -> callback vtable slot 136) is established independently; cross-library identity is the remaining gap.


### Two GTF2 comm::Proxy wrapper constructions and callback-offset caveat (2026-10-28)

Rechecked actual ARM disassembly of stock `gtf2` and the extracted factory ELF. GTF2 creates **two distinct proxy-wrapper variants**: in `0x6939b4`, it stores the original primary callback argument in wrapper `[r5,#0x48]` at `0x693c50`, then invokes imported `comm::Proxy::Proxy` at `0x693cd0`. A second construction path around `0x6934e4..0x6935d8` allocates **108 bytes**, stores its callback in wrapper `[r7,#0x48]` at `0x693548`, and invokes the same imported `comm::Proxy::Proxy` at `0x6935d8`. The latter passes a different lifecycle subobject, `r4+4`, as the fifth argument (`0x6935d0..0x6935d4`). This demonstrates that field `+0x48` is a **GTF2 wrapper-specific storage offset used in more than one wrapper**, not the factory receiver's callback field `+4`. A raw offset equality cannot link them.

Separately, the factory receiver vtable `0x52d70` has setter slot 0 (`0x3d47c`: `STR r1,[r0,#4]`) and dispatcher slot 1 (`0x40b80`). Selector 177 calls its stored callback's virtual slot 136. The `gtf2` primary callback object is passed as third argument `r2` to `0x6939b4` (`0x697ef4`) and saved into the wrapper. **Missing cross-module evidence**: a reader of the GTF2 wrapper's `+0x48` or a `comm` registration call that forwards it to factory setter `0x3d47c`. The local GTF2 function range `0x693000..0x69a000` contains two writes to `+0x48` (`0x693548`, `0x693c50`) and no direct `LDR [reg,#0x48]`; this does not exclude reads by external `comm` code or indirect addressing. Next investigate `libcomm.so` factory binding / registration, not speculative matching of offsets.


### Proxy wrapper object layout: corrected constructor interpretation (2026-10-28)

A fresh disassembly of the stock GTF2 at `0x693c20..0x693d10` distinguishes **two object bases**. `0x693c50` executes `STR r3,[r5,#0x48]`, retaining the primary callback in the GTF2 wrapper (`r5`). But the imported `comm::Proxy::Proxy` call at `0x693cd0` receives `r0=r4` (`MOV r0,r4` at `0x693cbc`), **not** `r5`. The constructor's fifth argument comes from the stack (`STR lr,[sp]` at `0x693cc4`) and represents the lifecycle listener. After the constructor returns, GTF2 overwrites the newly constructed proxy subobject's vptr at `[r4]` and `[r4,#8]` (`0x693d08..0x693d0c`) with its derived vtables. The literal at `0x693d64` resolves to `0x88e360`, the vtable used for the proxy subobject; its first entries include `0x6937cc` and `0x6938f4`, both destruction paths. This means the callback at wrapper `+0x48` is **not an argument to the comm::Proxy constructor**. It must be forwarded later by a derived wrapper method, or by a separate registration path. The prior claim that merely calling the constructor proves registration is unsupported. The extracted stock `libcomm.so` contains the mangled symbol for `comm::Proxy::Proxy(TrackedBase::IdentityArgs const&,ServiceRegistration const&,InterfaceStyle,LifecycleListener*)` and `comm::Proxy::connect`; this confirms the library implements the imported constructor but does not identify any factory callback setter invocation. Next trace the derived wrapper's virtual methods and the reader of `[wrapper+0x48]`, then follow its indirect factory call. This note corrects the object-base ambiguity without claiming the remaining cross-library link is solved.


### Derived comm proxy vtable: forwarding adapter, not callback registration (2026-10-28)

Re-read the original GTF2 ELF bytes and decoded the derived proxy vtables. `0x88e360` begins `0x6937cc, 0x6938f4, 0x18caf8, 0x18cb20, 0x18cb44, 0x18cb68, 0x10eef4`; the secondary subobject vtable begins at `0x88e384` and contains adjustment thunks subtracting 8 from `this` before forwarding to the same methods. The forwarding functions are concrete: `0x18caf8` reads `[r0,#4]`, checks null, then calls that object's virtual slot 2; `0x18cb20`, `0x18cb44`, `0x18cb68` read `[r0,#4]` and call slots 3, 4, 5 respectively. These accesses are to **offset +4 of the adapter object**, not to the GTF2 wrapper callback stored at `+0x48`. Destructor entries `0x6937cc` and `0x6938f4` do not implement the missing factory setter. The companion vtable at `0x88e608` contains `0x693988, 0x69394c, 0x18ca64, 0x18ca8c, 0x18cab0, 0x18cad4`, again with inherited forwarding functions. This rules out identifying the obvious derived vtable entries as direct reads of `[wrapper+0x48]`. The callback-transfer path is **still not established**; next inspect initialization and service-registration helper calls around `0x6935d8..0x693620` and `0x693cd0..0x693d10`, including factory ABI rather than conflating distinct offsets.


### Non-DP side effects in unresolved GTF2 IPC callbacks (static ARM32 verification, 2026-10-28)

The `gtf2-unresolved-callback-functions.csv` entries must **not** be interpreted as DP-only handlers. Direct disassembly of stock GTF2 shows additional calls *after* the `0x131390` DP write, all within the same callback invocation:

| Callback start | DP write (field offset/type) | Subsequent operations, in execution order |
|---|---|---|
| `0x695898` | `0x02000174` at `0x6958b0` (`payload+0`, u16) | `0x151558`, `0x14eb5c`, then `0x15ff7c(payload+0 u16, payload+2 u16)` |
| `0x696540` | `0x0200017d` at `0x696558` (`payload+1`, u8) | `0x151558`, `0x14eb98`, then `0x18f3d0` with the callback argument pointer |
| `0x6965a8` | `0x02000175` at `0x6965c0` (`payload+2`, u8) | `0x151558`, `0x14ec58`, `0x1dde40(payload+3 u8)`, `0x151558`, `0x14ec58`, `0x1ddea0(payload+4 u8)` |
| `0x696b6c` | `0x020001cb` at `0x696b84` (`payload+0`, u8) | `0x1562d8(payload+0 u8)` (additional constant loaded at `0x696b8c`) |
| `0x696c00` | `0x020001d5` at `0x696c18` (`payload+0xa`, u8) | `0x151558`/`0x14eb5c` and `0x163488(index=0,payload+4 u8)` at `0x696c30`; repeats for index=1/payload+5 at `0x696c48` and index=2/payload+8 at `0x696c60`; callback continues beyond `0x696c6c` |
| `0x696f4c` | `0x02000224` at `0x696f64` (`payload+5`, u8) | `0x151558`/`0x14eb78`, `0x18bb88` with payload bytes +0,+1,+2,+3 at `0x696f88`; `0x151558`/`0x14eca8`, `0x1a5e10(payload+5)` at `0x696f9c`; `0x151558`/`0x14ec38`, `0x1d7f4c(payload+5)` at `0x696fb8` |

These are **verified call sites and input-byte dependencies**, not yet semantically named actions. In particular `0x696f4c` forwards one incoming event to at least three other handlers in addition to its DP write, and `0x696c00` fans one event into indexed calls. This is evidence that the true IPC event reaction graph has non-DP edges; a DP-ID-only routing CSV cannot be treated as a complete event-effects inventory. The next static step should resolve the targets (`0x163488`, `0x18bb88`, `0x1a5e10`, `0x1d7f4c`) and add confirmed semantics only after their bodies are inspected. No QEMU execution is implied.
