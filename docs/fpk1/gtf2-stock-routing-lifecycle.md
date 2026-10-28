# GTF2 stock event routing and scene binding: binary-backed architecture

## Executive finding

The stock binary does **not** contain an established single `IPC → DP → scene → property` table. Our CSV is a **reverse-engineered relational join** across callback writes, DP dispatch branches, scene-wrapper constructor fields and HMI uses. Treating the CSV as a literal runtime table would be incorrect.

**Static:** callback logic, most DP constants, dispatcher comparisons/branches, embedded node-path and property-name strings, and owner-relative wrapper field offsets.

**Dynamic:** IPC payload values, allocated object addresses, the receiver pointer held at `wrapper+0xb8`, and calls through receiver virtual method tables. The exact moment and mechanism of assigning `+0xb8` remain **unproven**.

## Observed code, separated by lifecycle phase

### A. Source event and DP dispatch

- QNX IPC/RTE callback family: `asi.gss.ipc.rte.hmi.IHmiKss`.
- Callback code reads fields from an incoming payload and writes DP IDs. Current inventory: **176 distinct DP IDs**. These are source writes, not proof of 176 Kanzi properties.
- Main HMI dispatcher around `0x570000–0x577000` selects event handlers by DP ID, sometimes by literal comparisons and sometimes by arithmetic on a loaded literal.
- Example: `0x020002ce` is computed by subtracting 4 from `0x020002d2` and routes to `0x586c40`.
- The dispatcher and its constant set are static code. The incoming DP ID and payload values are dynamic.

### B. Wrapper construction and metadata

The two string setters are tiny, separate functions:

```asm
6343d8  mov r3,r0
6343dc  add r0,r0,#0x8c    ; path string field
6343e0  ldrb r2,[r3,#6]
6343e4  orr r2,r2,#2
6343e8  strb r2,[r3,#6]
6343ec  b 0x10da48        ; string assignment

6343f0  mov r3,r0
6343f4  add r0,r0,#0x78    ; property-name string field
6343f8  ldrb r2,[r3,#5]
6343fc  mvn r2,r2,lsl #25
634400  mvn r2,r2,lsr #25
634404  strb r2,[r3,#5]
634408  b 0x10da48        ; string assignment
```

These functions **assign string metadata**. They do **not**, by themselves, prove that a scene node has been looked up or activated.

Example ESP wrapper constructor at `0x2945fc–0x29465c`:
- Path literal slot `0x293ee8`: `MV_ClusterFull.StatusBar.line1_auchEarlyWelcome.ESP`.
- Path setter call `0x29461c → 0x6343d8`.
- Property literal slot `0x293ef0`: `ESP`.
- Property setter call `0x294648 → 0x6343f0`.
- Owner field offset literal slot `0x293ef4`: `0x453b8`.
- Store `0x29465c: str r0,[r4,r1]` places the wrapper pointer at owner `+0x453b8`.

This is **initialization code executed at runtime using compile-time strings and offsets**. Whether it runs only at process startup or again when a scene is recreated requires call-chain and runtime lifecycle evidence.

### C. Runtime receiver attachment is separate

```asm
6218b8  ldrb r3,[r0,#6]
6218bc  str  r1,[r0,#0xb8] ; attach/change receiver pointer
6218c0  orr  r3,r3,#0x40
6218c4  strb r3,[r0,#6]
6218c8  bx   lr

6218cc  ldr r0,[r0,#0xb8] ; fetch receiver pointer
6218d0  bx  lr
```

The existence of `0x6218b8` proves that the receiver field is **mutable at runtime**, and `0x6218cc` proves that handlers fetch its current value. The writer may be invoked indirectly (e.g. via a virtual method), so a missing direct `BL 0x6218b8` is not evidence that it never runs.

**Unresolved:** who calls the receiver attachment path, whether it resolves path/name via a Kanzi node lookup, whether it is performed eagerly or lazily, and how it handles scene changes/unload/reload. Do not claim that the `+0xb8` pointer is resolved at startup without that evidence.

### D. Dispatch to receiver, including virtual call

The ESP DP `0x020002cd` handler:

```asm
586bf0  bl 0x2bae28        ; obtain owner
586bf4  ldr r3,[pc,...]    ; 0x453b8
586bf8  ldr r0,[r0,r3]     ; owner-relative wrapper
586bfc  bl 0x6218cc       ; receiver = wrapper->receiver
586c00  ldr r3,[r0]       ; receiver vtable
586c04  mov r10,r0
586c08  ldr r7,[r3]       ; virtual method slot 0
...
586c38  blx r7             ; invoke receiver
```

This proves the receiver is read at event handling time and invoked through a virtual method. It **does not** prove that the virtual method is Kanzi's final property setter, or establish all value conversions/guards. The agreed reverse-engineering endpoint is the **named property**, not its rendering internals.

### E. Example fully joined route

`TelltaleHMI_Display → DP 0x020002cd → HMI 0x586bf0 → owner+0x453b8 → wrapper(path=MV_ClusterFull.StatusBar.line1_auchEarlyWelcome.ESP, property=ESP) → receiver pointer +0xb8 → virtual call`.

Root scene is parsed from the stored node path. This is **not** an observation that `MV_ClusterFull` is active at that instant.

## Coverage, precision, and limits

The current 176-DP source inventory and automated owner-offset join produce **33 DP IDs with candidate scene/property associations**, 36 distinct property names, and two observed scene roots (`MV_ClusterFull`, `RV_ClusterFull_Additional`). The other **143 source DP IDs** remain unresolved at the scene-property level. The 33 include bounded handler-window candidates and must not all be promoted to independently verified links.

The direct 24 plus arithmetic 25 dispatcher routes cover only 49 known main-dispatch entries; they are not a complete accounting of all 176 source DP IDs. Some events may update non-scene state or use different dispatch paths.

**Proof levels:**
- `verified`: source DP → exact handler branch → exact wrapper owner offset → constructor path + property literals.
- `candidate`: handler-local getter/constructor join without full CFG proof.
- `unknown`: DP source only; no proven scene property.
- `not-scene`: only after positive proof of another consumer, never inferred from a missing join.

## Remaining investigations required to reconstruct the *full process*

1. Identify all **indirect references/callers** of the receiver-attachment function `0x6218b8` and its virtual entry; find the code that resolves scene path and property name.
2. Trace that caller back to **scene lifecycle hooks** (load, activate, unload, recreate) to establish when attachment occurs and how stale pointers are invalidated.
3. Trace registration of the **IHmiKss IPC callbacks** and the DP subscription/notification path to the HMI dispatcher.
4. Recover alternate DP dispatch and non-Kanzi consumers for the 143 unjoined source DP IDs.
5. Audit the candidate 33 event joins with exact control-flow boundaries; export a machine-readable evidence ledger.
6. Validate runtime ordering with **instrumentation** in QEMU or stock logs: wrapper construction → receiver attachment → incoming event → virtual call → scene transition. Static disassembly alone cannot establish the exact temporal sequence.

**Do not overstate completeness:** the stock architecture is substantially understood, but the precise receiver binding lifecycle and complete source-DP coverage are not yet proven.

## New proof: receiver attachment is a shared virtual interface

The apparent absence of direct `BL 0x6218b8` callers is explained by a concrete vtable pattern in the original stock ELF. Searching for the little-endian function pointer `0x006218b8` yields **63 occurrences**, all in the binary's vtable-like data region. Each occurrence is at **offset +0x30 from the start of a distinct table**, and all 63 have plausible code pointers in neighboring method slots.

Examples:

| Vtable start | Binding slot (+0x30) | Slot 0 implementation |
| --- | --- | --- |
| `0x881b68` | `0x881b98 → 0x6218b8` | `0x622570` |
| `0x881bb8` | `0x881be8 → 0x6218b8` | `0x628a38` |
| `0x881c08` | `0x881c38 → 0x6218b8` | `0x62b240` |
| `0x88ae90` | `0x88aec0 → 0x6218b8` | `0x62373c` |

The common binding method body is:

```asm
6218b8  ldrb r3,[r0,#6]
6218bc  str  r1,[r0,#0xb8]   ; store dynamic receiver pointer
6218c0  orr  r3,r3,#0x40
6218c4  strb r3,[r0,#6]     ; mark flag bit 6
6218c8  bx   lr
```

The getter `0x6218cc` simply loads `[r0,#0xb8]`. Thus, **receiver attachment is a virtual operation implemented identically across at least 63 wrapper classes**. This strongly indicates a shared interface/base-class method, but does not identify the caller or prove whether it is invoked on scene creation, scene activation, or lazily on demand.

**Evidence strength:** all 63 function-pointer occurrences, table layout and method bodies were checked directly against the original GTF2 ELF. The repeatable verifier is `tools/fpk1/research/gtf2/verify_receiver_vtables.py`:

```sh
python3 tools/fpk1/research/gtf2/verify_receiver_vtables.py /path/to/gtf2
python3 tools/fpk1/research/gtf2/verify_receiver_vtables.py /path/to/gtf2 --csv
```

**Next precise reverse-engineering step:** search ARM indirect call sites loading slot `+0x30` from a wrapper's vtable, follow the call's `r1` producer backward to the scene lookup result, and then find the lifecycle caller. Avoid treating an ordinary function pointer occurrence as proof of invocation or a timestamp.

## Indirect-call search caveat: ARM BLX register is printed as unknown

A new binary-wide inspection of the sectioned GTF2 disassembly found that the installed `llvm-objdump` decodes ARM register-indirect `BLX` instructions (e.g. `e12fff33` = `BLX r3`) as `<unknown>`. Thus, a textual grep for `blx r3` **misses real indirect call sites**. Inspect instruction words directly instead.

A broad scan for `LDR rN,[rM,#0x30]` followed within 12 instructions by `0xe12fff3N` found **1,250 candidate indirect calls** in the whole disassembly. This is *not* a count of calls to receiver binder `0x6218b8`: many unrelated C++ classes have a method in slot `+0x30`. The virtual-table object type and receiver provenance must be proved before attributing any particular call to the binding method.

Representative raw instructions:

```asm
111564: e5903000    ldr r3,[r0]         ; read object's vtable
111568: e3a0100a    mov r1,#10
11156c: e5933030    ldr r3,[r3,#0x30]  ; load virtual slot +0x30
111570: e12fff33    blx r3             ; objdump labels <unknown>
```

**Next investigation target:** identify constructor-installed vtable pointers for the 63 wrapper classes, then track call sites operating on objects of those classes. A generic slot-number scan alone cannot establish binder callers or lifecycle timing.

## Constructor-time descriptor dispatch: distinct from receiver attachment

Further stock ARM tracing identifies a separate virtual method used immediately after constructing the scene-property wrapper:

```asm
; ESP property construction, owner in r4
294618  bl 0x6343d8       ; set full scene node path
294648  bl 0x6343f0       ; set exact property name "ESP"
29465c  str r0,[r4,r1]    ; owner field +0x453b8 = wrapper
294660  ldr r1,[pc,...]   ; r1 = 0x874100 (static binary descriptor)
294664  bl 0x62fc60      ; invoke virtual method +0x3c on wrapper
```

```asm
62fc60  cmp r1,#0
62fc68  popeq {r4,pc}
62fc6c  ldr r3,[r0]       ; wrapper vtable
62fc70  ldr r3,[r3,#0x3c] ; per-class descriptor initialization method
62fc74  blx r3            ; objdump shows <unknown>
```

In the **63 vtables** with common receiver attachment slot `+0x30 → 0x6218b8`, slot `+0x3c` instead points to **62 distinct implementations** (all executable code addresses). For example, `0x881bb8+0x3c → 0x65d8d0`; this implementation reads typed fields from `r1` and conditionally invokes class-specific setters depending on flags in the object. This is concrete evidence for a **per-class constructor-time initialization/descriptor pass**.

The static argument `0x874100` is a data block containing zero values and other constants, not the scene node path string and not a proven resolved Kanzi node pointer. Therefore, do **not** interpret the `0x62fc60` call as the receiver binding operation: the latter is a separate method at slot `+0x30`, and its caller/timing remain unresolved.

The demonstrated order for ESP is: **create wrapper → set scene path → set property name → store wrapper in owner → apply static descriptor via slot +0x3c**. Runtime receiver binding and IPC event delivery happen through other methods. Whether descriptor values represent defaults, constraints, or initial runtime state depends on the specific wrapper class; avoid assigning a universal semantic to the block without tracing its fields.

## Resolved: exact ESP receiver binder call in owner constructor

The previously unknown caller of the shared virtual binder **is present in the large owner constructor**. In the ESP block, the compiler interleaves unrelated field writes between setting up the virtual call and executing `BLX`, which explains why short-window searches missed it.

The full, independently verified ARM instruction/data chain is:

| Address | Operation | Proven effect |
| --- | --- | --- |
| `0x293ed0` | literal `0x45368` | owner field base used for `r8` |
| `0x2945bc` | `add r8,r8,#0x50` | `r8 = 0x453b8` (ESP wrapper field) |
| `0x29465c` | `str r0,[r4,r1]` | store constructed ESP wrapper at owner+`0x453b8` |
| `0x294664` | `bl 0x62fc60` | descriptor dispatch through virtual slot `+0x3c` |
| `0x294670` | `ldr r3,[r4,r8]` | fetch ESP wrapper |
| `0x293ef8` | literal `0x45644` | embedded receiver subobject offset before increment |
| `0x29469c` | `add r1,r1,#4` | receiver offset becomes `0x45648` |
| `0x2946a0` | `add r1,r4,r1` | receiver address `owner+0x45648` |
| `0x294698` | `ldr r3,[r3]` | wrapper's vtable |
| `0x2946b4` | `ldr r3,[r3,#0x30]` | virtual receiver attachment slot |
| `0x2946dc` | `e12fff33` (`BLX r3`) | **invoke receiver binder** |
| `0x6218bc` | `str r1,[r0,#0xb8]` | save embedded receiver pointer into wrapper |
| `0x6218cc` | `ldr r0,[r0,#0xb8]` | subsequent DP handler reads same pointer |

The virtual slot `+0x30` resolves to `0x6218b8` in 63 verified wrapper vtables. The call in this ESP constructor is therefore a concrete attachment of the **owner-embedded receiver object** (not a scene node lookup). The runtime DP handler `0x586bf0` later fetches this pointer from the same ESP wrapper and invokes its receiver's virtual method.

**Important lifecycle distinction:** the receiver is attached *during owner construction*, following static property descriptor initialization. This proves attachment does not require waiting for the first IPC event. It does **not** prove when the owner constructor itself is executed relative to loading/activating the Kanzi scene, nor that the receiver subobject is the final Kanzi node. The scene path and property name remain separately stored as wrapper metadata.

Verifier: `tools/fpk1/research/gtf2/verify_esp_receiver_binding.py`, tested against original stock ELF; all instruction opcodes, literal offsets and the 63 shared method-pointer occurrences match.

### Additional candidate attachment call sites

A broad binary-wide scan found **66** slot-`+0x30` indirect call sites with the pattern `ldr wrapper,[owner,offset]`, `mov r0,wrapper`, `ldr vtable,[wrapper]`, `ldr method,[vtable,#0x30]`, `BLX method`, and `r1` computed from the owner. This is strong evidence that owner-embedded receiver attachment is a repeated generated constructor pattern, but these 66 sites are not all independently type-verified. Do not equate them with the number of DP IDs or the 63 wrapper classes.

## Resolved: the owner is a guarded lazy singleton

A direct call-graph scan of the stock ARM ELF establishes the owner construction path:

```asm
2bae28  push {r4,lr}
2bae2c  ldr r4,[pc,#0x40]    ; r4 = 0x00afb38c (guard)
2bae30  ldr r3,[r4]
2bae34  tst r3,#1
2bae38  bne 0x2bae6c       ; initialized -> return existing owner
2bae3c  mov r0,r4
2bae40  bl 0x10e69c       ; acquire guard
2bae44  cmp r0,#0
2bae48  beq 0x2bae6c
2bae4c  ldr r0,[pc,#0x24] ; r0 = 0x00b64040 (owner storage)
2bae50  bl 0x25ef60       ; huge HMI owner constructor
2bae54  mov r0,r4
2bae58  bl 0x10f0e0       ; release guard
2bae5c  ldr r0,[pc,#0x14] ; owner
2bae60  ldr r1,[pc,#0x14] ; destructor 0x2432c8
2bae64  ldr r2,[pc,#0x14] ; DSO handle 0xa65a90
2bae68  bl 0x10e1d4       ; register destructor
2bae6c  ldr r0,[pc,#4]    ; return owner 0x00b64040
2bae70  pop {r4,pc}
```

The guard acquire/release and destructor registration have the characteristic shape of a C++ local-static singleton, but the above addresses and branches are directly observed, not merely inferred from the ABI.

A full direct ARM `BL` scan found **21,527 calls to getter `0x2bae28`** and exactly **one direct call to owner constructor `0x25ef60`**, at `0x2bae50`. The same getter is called from a short initialization sequence at `0x222074` and from event-handling code (e.g. `0x129758` and ESP `0x586bf0`). The construction code is therefore centralized and **runs at most once per initialized guard state**, not once per IPC event.

Combining this with the ESP constructor trace yields:

**first invocation of getter** → **guard acquisition** → **construct owner `0x25ef60`** → **construct ESP wrapper and set path/property/descriptor** → **attach owner-embedded receiver via virtual slot `+0x30`** → **release guard** → **subsequent DP events retrieve the same owner and receiver**.

This resolves *who creates the owner and how its construction is guarded*. It does **not** yet establish whether the `0x222070` startup-like function executes before IPC callback registration or Kanzi scene activation. Also, the owner-embedded receiver pointer is not itself proof that the Kanzi scene node has been resolved.

Verifier: `tools/fpk1/research/gtf2/verify_owner_singleton.py`, executed successfully on original stock GTF2 ELF (including the direct-call counts).

## Resolved: owner construction precedes entry into main event loop

The stock executable has a concrete startup chain:

```
0x68c860 (outer startup/loop routine)
  0x68c894 BL 0x114650  (initialization)
    0x1146b8 BL 0x222070
      0x222074 BL 0x2bae28 (guarded owner getter)
        0x2bae50 BL 0x25ef60 (owner constructor on first call)
    0x1146bc BL 0x14aaf4
    0x1146c0 BL 0x69b71c
    0x1146c4 BL 0x222ea4
    ... further initialization
  0x68c898 check init return status
  0x68c8b0 loop condition
  0x68c8c0 BL 0x11459c (event processing loop body)
  0x68c8d0 branch back to loop condition
```

This proves that, **on the normal successful startup path**, the singleton HMI owner and its ESP wrapper/embedded receiver are constructed before the program enters the event-processing loop at `0x68c8b0`. In particular, the owner is not first constructed by a later DP event on this path. The singleton getter remains available for other callers, and it is guarded against repeated construction.

The `0x114650` routine calls several more initialization functions after `0x222070`, so **this does not establish when IPC callbacks are registered or when the Kanzi scene is loaded/activated**. Nor does the loop ordering alone prove that no asynchronous IPC callback can arrive before the loop; that would require tracing registration/thread creation and synchronization. The verified statement is strictly **owner construction before the primary event loop**.

Reproduction:

```sh
python3 tools/fpk1/research/gtf2/verify_startup_event_loop_order.py /path/to/gtf2
```

The verifier checks all eight direct `BL` edges, the main-loop branch instructions, and the order of initialization and loop entry against the original ELF. Tested successfully on the stock binary.

## Startup event hook: TriggerContextChange

Within the startup initialization function `0x114650`, after the HMI singleton has been constructed via `0x1146b8 → 0x222070 → 0x2bae28`, the executable installs a named context-change callback. This is a **separate event hook**, not yet proven to be part of `IHmiKss` IPC or Kanzi scene binding.

```asm
114c00  bl 0x11453c          ; further object setup
114c08  bl 0x1140b0          ; further object setup
114c0c  ldr r3,[r6]         ; access global object
114c18  ldr r3,[r3,#0x10]   ; virtual slot +0x10
114c1c  blx r3               ; obtain/check registration target
114c20  cmp r0,#0
114c24  beq 0x114c74        ; skip if unavailable
114c3c  blx r3               ; get registration target
114c44  ldr r1,[pc,#0xbc]   ; string "TriggerContextChange" at 0x7bdf37
114c54  ldr r7,[r3,#0x10]   ; virtual method +0x10
114c58  bl 0x10e7bc         ; construct temporary name/string object
114c60  mov r1,r4           ; name object
114c64  ldr r2,[pc,#0xa0]   ; callback pointer 0x1152b4
114c68  blx r7               ; invoke virtual registration-like method
114c70  bl 0x10f074         ; destroy temporary string
```

The callback `0x1152b4` calls `0x11511c` and then tail-branches to `0x114074`. The stock ELF verifies the name bytes, pointer literal, indirect call opcode and callback's direct call. This is a concrete **startup-time event-hook setup** after owner construction, and the code gracefully skips it if the target is unavailable.

**Caution:** the virtual method at `+0x10` has not been identified by class/vtable; its exact API semantics (subscribe/register vs another operation) remain to be verified. In particular, do not label this as `IHmiKss` IPC registration or as Kanzi scene activation. The remaining question is to trace `IHmiKss` callback object construction/registration and scene resource loading independently.

Reproduce with `tools/fpk1/research/gtf2/verify_startup_context_hook.py /path/to/gtf2`. Verified on stock GTF2 ELF.

## Startup investigation: concrete Kanzi resource name and IPC interface descriptor

Two previously untraced inputs have now been tied to executed ARM code in the stock ELF.

### DisplaySupervisor.kzb in the startup path

The startup function `0x114650` references a real KZB filename, `DisplaySupervisor.kzb` (literal `0x7bdeb5`), **after** calling the HMI singleton constructor at `0x1146b8`.

```asm
114a00  ldr r1,[pc,#0x2e0]   ; literal at 0x114ce8 -> "DisplaySupervisor.kzb"
114a04  bl 0x141fd8         ; wraps a C++ string, forwards to 0x141fbc
...
114a1c  cmp r0,#1
114a20  bne 0x114a54        ; conditional resource-related branch
114a44  bl 0x142cec         ; subsequent operation using prepared objects
```

The helper `0x141fd8` constructs a temporary C++ string and calls `0x141fbc`, so `0x114a04` **passes the KZB filename into an object**. It is not yet proven whether `0x141fbc` stores a resource name, schedules loading, or opens the KZB. Nor is `0x142cec` yet proven to activate the Kanzi scene. Therefore this establishes the resource-name handoff and startup order, **not the precise time of scene availability**.

### IHmiKss interface descriptor in the large HMI owner constructor

The stock binary contains a concrete two-name descriptor at `0xa7e838`:

```
[a7e838] = 0x88f55d -> "asi.gss.ipc.rte.hmi.IHmiKss"
[a7e83c] = 0x88f579 -> "asi.gss.ipc.rte.hmi.IHmiKssReply"
```

A literal at `0x50fe8c` contains `0xa7e838`. In the large HMI owner constructor `0x25ef60`, the code at `0x5107f8` loads this descriptor and stores it in an owner field:

```asm
5107f8  ldr r2,[pc,#-0x974] ; literal 0x50fe8c -> 0xa7e838
5107fc  str r2,[r4,r3]      ; store descriptor pointer into owner
510804  mov r2,#1
510808  str r2,[r4,r3]      ; set adjacent owner field
```

This proves the **IHmiKss/IHmiKssReply interface descriptor is wired during HMI owner construction**. It is **not** by itself evidence that the IPC transport is already connected or callbacks subscribed: the descriptor can be installed before transport initialization.

Together, these traces give a stronger ordering:

**startup** → **construct HMI singleton (including interface descriptor, scene-property wrappers and embedded receivers)** → **pass `DisplaySupervisor.kzb` to resource/configuration object** → **additional startup operations, including `TriggerContextChange` hook** → **primary event loop**.

The remaining high-value proof points are: identify the call to the IPC transport's actual subscribe/connect method, and trace `0x141fbc`/`0x142cec` to the concrete KZB open and scene-activation APIs. An asynchronous IPC worker could still process messages before the main loop; the above order does not exclude that.

Verifier: `tools/fpk1/research/gtf2/verify_ipc_descriptor_and_kzb_startup.py`, checked against original stock ELF.

## Resolved: startup explicitly waits on an RTE object

Within the same startup routine `0x114650`, after constructing the HMI owner and before later context/design setup, the original ARM code enters an explicit wait loop. **Correction: this loop checks the occupancy count of an RTE-related queue, not a generic readiness flag:**

```asm
114ab0  bl 0x13d098         ; obtain service/global object
114ab4  bl 0x14199c         ; service-related operation
114ab8  mov r0,r5
114abc  bl 0x10e870
114ac0  mov r0,#2
114ac4  mov r1,#0
114ac8  bl 0x10dcc4        ; waiting/yield operation, exact API unverified
114acc  bl 0x13d098
114ad0  bl 0x13a614        ; test RTE object state
114ad4  cmp r0,#0
114ad8  bne 0x114ab0      ; repeat while not ready
```

The occupancy test is particularly simple:

```asm
13a63c  ldr r0,[r4,#0xc]  ; read object field +0x0c
13a640  subs r0,r0,#0
13a644  movne r0,#1      ; normalize to boolean
13a648  pop {r4,pc}
```

After the loop, `0x114b08–0x114b1c` computes a difference between previously saved timing values and logs the literal **`%dms waited on RTE`** (at `0x7bdefa`) through `0x10e264`. This directly grounds the interpretation as an **RTE wait**; it is not merely inferred from a field or generic loop. The wait body also performs other service operations; their exact role is not yet known.

This sharpens the startup chain:

**construct HMI owner/receiver objects** → **perform resource/configuration setup** → **wait for RTE state to clear** → **query active design/variant and set context hooks** → **main event loop**.

**Important boundary (corrected after tracing writers):** `RTE queue+0x0c == 0` is the exit condition, and `+0x0c` is a queue occupancy count (see below), not a generic ready flag. The diagnostic calls it RTE waiting, but this does **not** prove that all `IHmiKss` subscriptions are registered, that incoming events cannot arrive asynchronously, or that Kanzi scene nodes have been activated. The `DisplaySupervisor.kzb` reference nearby is passed through a temporary string/configuration path and should not be treated as proof of actual KZB loading.

Reproducible verifier: `tools/fpk1/research/gtf2/verify_rte_startup_wait.py`; executed successfully against the original stock GTF2 ELF.

## Correction and proof: RTE wait observes a queue count

Following **writers**, not just the reader `0x13a614`, resolves the semantics of the field at `+0x0c`.

- `0x13d098` is a lazily allocated singleton object stored through global pointer `0xab6114`. Its allocator requests 272 bytes and calls `0x13cf58`.
- Constructor `0x13cf58` invokes `0x13ce74` to initialize a dynamic ring-buffer-like collection with four header words and a capacity field at `+0x10`. `0x13ce74` initializes `+0x0c` to zero and copies it from a source collection when appropriate.
- **Producer `0x13ce08`** checks the count at `+0x0c` against `capacity-1` (`0x13ce18–0x13ce2c`), grows the allocation through `0x13ccac` if needed, writes an entry through `0x13c9c4`, advances the ring index at `+0x08` (wrapping to zero at capacity), and **increments `+0x0c` at `0x13ce60–0x13ce64`**.
- Startup passes the singleton into `0x141608` at `0x114a98`; `0x141608` invokes the producer `0x13ce08` at `0x14165c`. Thus the startup path itself can populate this queue before waiting.
- The wait loop `0x114acc → 0x13d098 → 0x13a614` checks this queue's `+0x0c` and repeats while the count is nonzero.

**Conclusion:** `%dms waited on RTE` describes waiting for **queued RTE-related work to drain**, not waiting for a readiness bit to be cleared. The producer and count interpretation are directly established by ARM instructions. The **specific consumer/decrement operation and its thread/IPC ownership remain untraced**; therefore do not infer that every IPC subscription is ready or that Kanzi has loaded its scene when the count reaches zero.

This supersedes the earlier wording in this document that described `+0x0c` as an unnamed readiness state. Reproduce with `tools/fpk1/research/gtf2/verify_rte_queue_count.py /path/to/gtf2`; tested against the stock GTF2 ELF.

## Resolved: RTE queue is consumed synchronously by the startup loop

The missing dequeue has been located at `0x141eec–0x141f30`, inside **`0x14199c`**, which is **directly called from the startup wait loop at `0x114ab4`**. The exact sequence is:

```asm
114ab0  bl 0x13d098       ; obtain queue singleton
114ab4  bl 0x14199c       ; process pending queue work (consumer)
...
114acc  bl 0x13d098       ; obtain same singleton
114ad0  bl 0x13a614       ; return queue occupancy != 0
114ad4  cmp r0,#0
114ad8  bne 0x114ab0     ; repeat while nonempty
```

The consumer's dequeue epilogue:

```asm
141eec  ldr r3,[r4,#0xc] ; queue count
141ef0  cmp r3,#0
141ef4  beq 0x141f34     ; no element to remove
141ef8  ldr r2,[r4,#4]   ; read index
141efc  mov r0,#52       ; element size
141f00  ldr r3,[r4]      ; element storage
141f04  ...              ; compute address at index*52
141f08  bl 0x13a378     ; destroy/clean up element
141f0c  ldr r3,[r4,#4]
141f10  ldr r2,[r4,#0x10] ; capacity
141f14  add r3,r3,#1
141f18  str r3,[r4,#4]   ; advance read index
141f1c  cmp r3,r2
141f20  movhs r3,#0
141f24  strhs r3,[r4,#4] ; wrap index at capacity
141f28  ldr r3,[r4,#0xc]
141f2c  sub r3,r3,#1
141f30  str r3,[r4,#0xc] ; decrement queue count
141f34  mov r3,#0
141f38  strb r3,[r4,#0x14] ; clear a queue state byte
141f3c  mov r0,r4
141f40  bl 0x13e7b0     ; subsequent operation
```

Thus the queue has an independently verified producer `0x13ce08` and consumer `0x14199c`; the latter executes **on the startup thread's synchronous call path**, without requiring a hypothetical background consumer to explain how the count falls. It may still invoke other services via virtual dispatch, and there may be asynchronous producers; neither is excluded.

The startup wait is more precisely described as **actively processing RTE-related queued work until the queue is empty**. It is *not* a readiness-bit wait, and an empty queue alone does not prove that `IHmiKss` callbacks are subscribed or that the Kanzi scene is ready.

Verified against original stock ELF using `tools/fpk1/research/gtf2/verify_rte_queue_consumer.py` (all direct branches and dequeue opcodes checked).

## RTE queue work-item layout and producer families

Tracing the **contents of the startup-enqueued work item** rather than only its queue counter establishes the following ARM sequence:

```asm
114a7c  mov r1,#8           ; input parameter for 0x14250c
114a84  bl 0x14250c        ; prepare a collection/argument
114a88  bl 0x13d098        ; RTE queue singleton
114a8c  mov r2,r5          ; pointer to startup-side object
114a90  mov r1,r6          ; prepared collection/argument
114a94  mov r3,#0          ; fourth argument = 0
114a98  bl 0x141608        ; enqueue/build work item

141640  mov r2,#52
141644  mov r0,r6          ; stack work-item address
141648  mov r1,#0
14164c  bl 0x10e678       ; clear 52-byte work item
141650  mov r1,r6
141654  mov r0,r4          ; queue
14165c  bl 0x13ce08       ; enqueue/copy record
141660  mov r0,r6
141664  bl 0x13a378       ; destroy temporary record
...
14168c  str r9,[r7,#0x30] ; store fourth argument in queued record +0x30
```

`0x141608` has exactly **two direct ARM BL callers** in the stock ELF: startup `0x114a98` (fourth argument zero) and `0x123474` (fourth argument loaded from a literal at `0x123504`). The lower-level queue producer `0x13ce08` has exactly **three direct ARM BL callers**: `0x1414e0`, `0x14165c`, `0x1417b8`. An additional higher-level work-item path `0x121d2c → 0x141870 → 0x141744 → 0x13ce08` is also present. These counts cover direct ARM `BL` instructions only, not possible indirect calls.

The queue consumer `0x14199c` examines several state bytes (`+0x14`, `+0x54`, `+0x64`) and processes nested collections and virtual calls before removing the 52-byte head item at `0x141f08–0x141f30`. The work item is therefore **not just a boolean notification**. However, the *semantic type* of the startup item and its relationship to actual `IHmiKss` transport subscription are **still unknown**. In particular, `r3=0` is a verified input value, not a recovered event enum name.

Reproduce: `python3 tools/fpk1/research/gtf2/verify_rte_queue_record_sources.py /path/to/gtf2`. Tested against the original stock ELF: all 12 call edges, 16 instruction words and direct-call counts matched.
