# GTF2 callback construction: original ARM evidence

Original `gtf2` ELF has no section headers; its executable PT_LOAD starts at file offset 0, VMA `0x100000`. Disassembly was enabled locally by adding synthetic `.text` section metadata to a copy; original bytes and addresses were not modified.

## Callback constructor `0x6977a4`

- `0x6977a4`: `push {r4,lr}`.
- `0x6977b8`: `str r1,[r4,#0xc]` saves constructor argument at offset `+12`.
- `0x6977bc`: `str r2,[r4,#8]`, where `r2` is derived from literal `0x88e6b0` plus 632.
- `0x6977c0–0x6977cc`: `stm r4,{r2,r3}` stores two vtable pointers derived from `0x88e6b0` (`+8` and `+608` respectively) at object offsets 0 and 4.
- `0x6977cc`: calls `0x6998f4` for embedded subobject at `this+20`.
- `0x6977d0–0x6977f4`: initializes additional embedded objects at offsets `+28`, `+40`.

This proves the GTF2 callback object is **multiply polymorphic**: its first two words are different vtable pointers. The primary vtable is `0x88e6b8` (base `0x88e6b0 + 8`). Any comparison with the proxy's receiver must use the correct subobject address and vtable, not assume all callback interfaces use the same pointer.

## Allocating wrapper `0x69780c`

- `0x697814–0x69781c`: requests allocation of **52 bytes** through `0x10dcac`.
- `0x697820–0x697828`: calls constructor `0x6977a4` with the original `r1` argument.
- `0x69782c–0x69783c`: passes constructed object to `0x10eb7c` with literal at `0x697848` = `0x68dbe4`; purpose of this registration helper remains unknown.

## Proxy receiver API

The proxy's own vtable at `0x53d70` has slot 0 (`0x3d47c`), exactly `str r1,[r0,#4]; bx lr`, proving a setter for its receiver field. Slot 3 (`0x3d484`) reads this same field and calls virtual offset `0x230` or `0x234`. Slot 1 (`0x40b80`) uses receiver slot 28 for dispatch index 127.

**Unresolved:** the call chain from GTF2 `0x69780c` / its owning initialization code to the proxy setter, and whether the stored receiver pointer is the callback object's primary (`0x88e6b8`) or secondary vtable subobject. This must be established before declaring `0x43b5c -> 0x696f4c` a direct call.
