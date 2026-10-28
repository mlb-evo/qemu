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
