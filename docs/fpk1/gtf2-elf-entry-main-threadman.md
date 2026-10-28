# GTF2 ELF entry → main → ThreadManager (direct ARM evidence)

Source: original `STAGE2.1/bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Disassembled original executable PT_LOAD bytes (temporary synthetic .text section, original ELF bytes unchanged). These **entry/main details were not in the previous lifecycle narrative**.

## Entry and initialization before main

ELF `e_entry = 0x10f300`. ARM entry routine reads argc from `[sp]`, computes argv and envp by scanning the NUL-terminated argv vector (`0x10f304–0x10f324`), saves them in r4/r5/r6, then executes these indirect calls in this **static instruction order**:

| call site | literal callee | parameters/evidence | interpretation |
|---|---|---|---|
| `0x10f338–0x10f33c` | `0x10dc88` | argc, argv, envp already saved | runtime setup; exact semantics unresolved |
| `0x10f350–0x10f354` | `0x10e3e4` | `0xa644dc, 0xa644dc` | zero-length range: not 352 constructors |
| `0x10f360–0x10f364` | `0x10e630` | `0x7bca98` | likely fini registration, unverified |
| `0x10f374–0x10f378` | `0x10e3c0` | `0xa64a5c, 0xa64a60` | adjacent pointer range; semantics unresolved |
| `0x10f380–0x10f384` | `0x10d774` | `DT_INIT` | confirmed address |
| `0x10f394–0x10f398` | `0x10dae4` | `0xa644dc, 0xa64a5c` | 1408-byte `DT_INIT_ARRAY` range, **352 entries** |
| `0x10f3b8–0x10f3bc` | `0x1126b8` | r0=argc, r1=argv, r2=envp | **application main candidate** |
| `0x10f3c4–0x10f3c8` | `0x10efc0` | return value from main in r0 | runtime termination path |

The array bounds are `0xa64a5c - 0xa644dc = 0x580 = 1408` bytes. The **main is reached after** the direct `DT_INIT` and array-initializer calls. Actual function names and dynamic loader pre-entry activity are separate questions.

## Main `0x1126b8`: concrete sequence

1. At `0x1126b8`, saves registers and reserves ~3316 bytes of stack; receives argc and argv in r0/r1.
2. `0x1127d4` calls `0x755710` with string `Gtf2Started` (`0x7bd5c3`), prior to configuration handling. The exact API is not identified.
3. Constructs command-line/configuration descriptors. Strings directly referenced by this main include `gtf2` (`0x7bd599`), `hmi` (`0x8001f5`), `HMI application` (`0x7bd5cf`), `kdgui_2dmgr_wait` (`0x7bd5f0`), `kzb_search_path` (`0x7bd64a`), `gem_enable` (`0x7bd694`), `dp_monitor` (`0x7bd6cc`), `dev_hmi` (`0x7bd6f8`). **These are CLI option names, not evidence that the features are enabled**.
4. `0x112cbc–0x112cc4` calls `0x10f7b4` with original argc/argv after registering option descriptors. `0x112cc8` tests a stack byte and branches on the result; do not assume successful parse without following that byte's writer.
5. On the non-error branch, `0x112d2c–0x112d60` copies option flags and prepares configuration. `0x112dac` calls `0x10fc38` for cleanup of an object; it is **not** a verified application initialization call.
6. `0x112dac–0x112db4` checks `r4`, converting zero to -1 and skipping the following startup block if zero.
7. In the startup block, `0x112dc4–0x112dc8` conditionally calls `0x113e40` based on stack flag `[sp+0xb44]`. `0x112dec` calls `0x123e70` with a local object; **this function is a path/string normalization helper**, not AgentStarter initialization (it checks trailing slash at `0x123f30–0x123f38`). `0x112e18` calls `0x12e380`, previously identified as **ThreadMan run loop**. This is the direct **main → ThreadMan** link.
8. On return, main performs cleanup, logs conditionally, and returns `r4` at `0x112ef4`. The actual creation/registration of IPC and graphics objects must be traced through the functions called earlier; this document does **not** claim their initialization order.

## Implications for implementation

**Verified order constraint:** CRT startup / constructors → `main` option construction and parsing → conditional pre-loop operations → ThreadManager loop. **Do not** mark HMI ready merely when main begins, or when `Gtf2Started` string is emitted; neither proves IPC subscriptions, KZB completion or display readiness.

**Next nonduplicative work:** inspect `0x1122ec` and the main-called `0x10f7b4` option parser to identify default values and actual startup gates; trace ThreadManager creation and the exact first events in `0x12e380`, then join to already-known GSS activation and KZB state machine. Keep Stage3 beyond the single `startEfsDriver()` action out of scope.
