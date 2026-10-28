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
Immediately preceding this dispatch: `0x43a00 mov r0,#6` and `0x43a04 bl 0x3f34` allocate a six-byte region; `0x43a18–0x43a2c` zero its bytes 0..5, followed by `0x43a30 bl 0x40720`. This **supports** a six-byte argument payload but does not by itself prove the wire format or how the bytes are filled. Branches `0x439d0–0x43a88` condition the allocation/decoding path.

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
