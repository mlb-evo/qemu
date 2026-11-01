# GTF2 IPC proxy: slot 28 call sites (static evidence, 2026-10-28)

Source: Q7 0378 firmware ZIP, Stage2.1 imagefs, `lib/factories/libgssIpcRteHmiProxy.so`.
SHA-256 proxy: `188d610c523cbdd1b81ab89420e5fb1042753faeeb7edf9914ae595a449f33a2`; 348160 bytes.
GTF2 SHA-256: `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`; 10180269 bytes.
Both extracted with SIFS framed LZO and imagefs catalog parsing; no execution.

## ELF coordinate system
Proxy is ELF32 little-endian ARM EABI5 ET_DYN, stripped section headers; executable PT_LOAD file offset 0, vaddr 0, filesz 0x517a4; writable PT_LOAD offset 0x517a4, vaddr 0x527a4. All instruction addresses below are **ELF virtual addresses relative to shared-object load base**, not absolute runtime addresses. Executable segment file offsets equal listed virtual addresses for these call sites. Runtime ASLR/load address not determined.

## Confirmed call sites for callback vtable byte offset 0x70 (= slot 28, 32-bit entries)

### Path A, 0x43b3c–0x43b5c
```asm
43b3c ldr r3, [r5, #4]      ; callback receiver from dispatcher object
43b48 mov r0, r3            ; this = receiver
43b50 ldr r3, [r3]          ; receiver vtable
43b54 mov r1, r4            ; stack-local argument wrapper
43b58 ldr r3, [r3, #0x70]  ; slot 28
43b5c blx r3
43b60 mov r0, r4
43b64 bl 0x3ee0            ; wrapper cleanup
```
Immediately preceding this dispatch: `0x439fc mov r0,#6`, `0x43a00 ldr r1,[r4,r3]`, and `0x43a04 bl 0x3f34` allocate a six-byte region; `0x43a18–0x43a2c` zero its bytes 0..5, followed by `0x43a30 bl 0x40720`. This **supports** a six-byte argument payload but does not by itself prove the wire format or how the bytes are filled. Branches `0x439d0–0x43a88` condition the allocation/decoding path.

### Path B, 0x1ed2c–0x1ed44
```asm
1ed2c ldr r3, [r4, #4]      ; callback receiver
1ed30 add r2, r4, #8        ; additional argument
1ed34 ldrb r1, [sp, #0x5ef] ; byte argument
1ed38 mov r0, r3
1ed3c ldr r3, [r3]
1ed40 ldr r3, [r3, #0x70]  ; slot 28
1ed44 b 0x1c9b0
1c9b0 blx r3               ; shared indirect call site
```
**Important:** path B passes r1 as a byte and r2 as an address, whereas path A passes r1 as a stack wrapper. Thus the two sites are not necessarily the same callback interface. The receiver's dynamic vtable type must be established before attributing both to GTF2's vtable 0x88e6b8. Slot index alone is not a type identity.

## Unresolved
- Exact selector for path A, dispatch jump table, IPC envelope and serialization format.
- Proven receiver dynamic type and link to GTF2 callback vtable `0x88e6b8`.
- Whether path B is the same interface; do not merge it with path A.
- Symbolic method name, full six-byte payload provenance, and selector-to-slot mapping.
- The user-supplied GTF2 slot-28 target `0x696f4c` and DP-ID `0x02000224` remain earlier research claims pending independent cross-check against GTF2 disassembly in this evidence note.

Do not infer selector = slot + constant; a separate example uses selector 177 and slot 136, but that does not prove a mapping rule.

## Follow-up: precise branch and argument provenance

At `0x439b0` the proxy loads an object from `[r5+0x18]`; `0x439c0–0x439c8` invokes its virtual slot 6 (`[vtable+0x18]`) with `r1=sp+0x170f` (derived from `sp+0x1700-1`). The status byte `[r10+4]` is tested at `0x439cc–0x439d4`: nonzero branches to `0x43a70` (failure/cleanup path). If zero, byte `[sp+0x173f]` is tested at `0x439dc–0x439e4`; nonzero uses `0x40720` at `0x439f0` directly, whereas zero constructs a six-byte zero-filled buffer at `0x439f8–0x43a30`. `0x40720` begins with `ldr r3,[r0,#4]` and `cmp r1,r3` (`0x40720–0x40728`); it is **not proven to be a six-byte wire decoder**. Its behavior depends on object arguments and should not be labeled deserialization until analyzed. At `0x43a34–0x43a6c`, two stack words are checked and a further virtual/utility call may gate the success path. Finally `0x43b3c–0x43b64` constructs the stack wrapper and invokes slot 28.

The proxy also logs a value `128` at `0x43b2c`, but it is passed as `r1` to an indirect logging-like call and **must not be identified as the IPC selector** without further proof. Similarly `122` at `0x43928` is not a verified selector.

**Correction:** the allocation length instruction is at `0x439fc`, not `0x43a00`. The previous shorthand address was wrong; the actual ARM instruction at `0x43a00` is `ldr r1,[r4,r3]`.

## Confirmed dispatch-table index 127 (2026-10-28)

The entry to this callback branch has now been traced back to the proxy's 180-way ARM dispatch table in `0x40b80`:

- `0x40b9c`: `r6 = [r2]`; `0x40bcc`: `r7 = r1` (incoming dispatch index).
- `0x40c9c`: `cmp r7,#179`; `0x40ca0`: `addls pc,pc,r7,lsl #2`.
- Table starts at `0x40ca8`, so entry 127 is `0x40ca8 + 127*4 = 0x40ea4`.
- `0x40ea4`: `b 0x43968`; this branch eventually calls receiver virtual slot 28 at `0x43b5c` (`[vtable+0x70]`).

Thus **dispatch index 127 → branch 0x43968 → callback slot 28** is statically proven. `r7` comes directly from the second argument of the proxy dispatch function (`r1` at entry). Whether this is the original on-wire IPC selector or a preprocessed ID remains to be established from the caller of `0x40b80`; label it *dispatch index*, not proven wire selector. This is unrelated to log/source constants 122 and 128 found inside the branch.

`0x40720` is a generic shared helper called with multiple payload sizes (including 6 and 20 bytes at other sites), not an identified six-byte decoder. Its entry compares `r1` with `[r0+4]`; later `0x408d8` stores `{r0,r8}` into the receiver, consistent with buffer ownership/update. Avoid treating the six-byte zero-fill as a fixed wire payload layout.

## Dispatch function ABI and preprocessing, verified against original proxy ELF

`0x40b80` is not a simple direct branch stub. Its register/data provenance at entry is:

| PC | ARM operation | Evidence |
|---|---|---|
| `0x40b84` | `ldr r10,[r0,#0x18]` | `this+0x18` is a processing/status object |
| `0x40ba0` | `ldr r6,[r2]` | dereferences the third argument, storing message/context pointer in `r6` |
| `0x40bc0` | `mov r5,r0` | preserves dispatch object as `r5` |
| `0x40bcc` | `mov r7,r1` | preserves the **second ABI argument** as dispatch index |
| `0x40bd0` | `add r1,r6,#4` | prepares message/context bytes for a helper |
| `0x40bd8` | `bl 0x3fac` | constructs temporary wrapper |
| `0x40bf4` | `blx r9` | invokes virtual method of `[this+0x18]` object, vtable offset `0x10` (`0x40bd4`) |
| `0x40c04–0x40c10` | test `[r8+4]` | may leave to common failure handling before the dispatch table |
| `0x40c90` | `uxth r1,r0` | result of another virtual call is narrowed to 16 bits and passed to `0x3e98`; it is **not** the dispatch index |
| `0x40c9c–0x40ca0` | `cmp r7,#179`; `addls pc,pc,r7,lsl #2` | dispatch uses unchanged original `r1` argument |
| `0x40ea4` | `b 0x43968` | index 127 branch |
| `0x43b3c–0x43b5c` | receiver `[r5+4]`, vtable slot 28 | callback invocation |

**Strong conclusion:** Within `0x40b80`, the dispatch index 127 is **not derived from the payload, status byte, or a decoder return**: it is copied unchanged from the function's incoming `r1` at `0x40bcc`. This narrows the outstanding question to the upstream caller/virtual interface supplying argument `r1`. The third argument (`r2`) supplies a separate pointer-bearing message context. There is no direct `bl 0x40b80` in the proxy's disassembly, consistent with an indirect or externally invoked entrypoint; this absence alone does not prove a particular registration mechanism.

**Important caveat:** the earlier shorthand described `0x40b9c` as `ldr r6,[r2]`; the correct instruction address is `0x40ba0`. `0x40b9c` is `add lr,sp,#7040`.

## Breakthrough: `0x40b80` is a virtual method in the proxy's own vtable

The original ELF has two `PT_LOAD` segments: RX file offset/vaddr `0`, RW file offset `0x517a4` at virtual address `0x527a4`. Consequently RW virtual address `0x53d74` maps to **file offset `0x52d74`**, where the little-endian word is exactly `0x00040b80`. The ELF dynamic relocation table marks virtual `0x53d74` as `R_ARM_RELATIVE`; the loader will add the shared-object load base.

Adjacent entries (virtual addresses, pre-relocation values):

| Virtual address | Word | Vtable interpretation |
|---|---|---|
| `0x53d68` | `0` | plausible Itanium C++ offset-to-top (ABI hypothesis) |
| `0x53d6c` | `0` | plausible RTTI pointer (ABI hypothesis) |
| `0x53d70` | `0x3d47c` | virtual slot 0 |
| **`0x53d74`** | **`0x40b80`** | **virtual slot 1: 180-way IPC dispatcher** |
| `0x53d78` | `0x3d77c` | virtual slot 2 |
| `0x53d7c` | `0x3d484` | virtual slot 3 |
| `0x53d80` | `0x3ff98` | virtual slot 4 |
| `0x53d84` | `0x3fe94` | virtual slot 5 |

Thus the entrypoint is not merely an unreferenced local function: **the shared library publishes it through a relocatable virtual method table**. A caller can invoke this dispatcher via the object vtable slot 1, which explains why a direct `bl 0x40b80` need not exist. This is a distinct vtable from the *callback receiver* loaded from `[r5+4]` in `0x43b3c`: the `0x53d70` table belongs to the proxy dispatch object; the GTF2 receiver's table remains unverified.

Note: searching for `0x40b80` in file bytes yields offset `0x52d74`; confusing that file offset with ELF virtual address leads to a false conclusion. The relocation at virtual `0x53d74` independently verifies the table entry.
