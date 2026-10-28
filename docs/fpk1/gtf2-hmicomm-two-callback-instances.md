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
