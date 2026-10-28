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
