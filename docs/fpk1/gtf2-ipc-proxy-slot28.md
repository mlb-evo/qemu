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
