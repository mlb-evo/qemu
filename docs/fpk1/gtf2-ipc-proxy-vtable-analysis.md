# Proxy vtable analysis

Static ARM disassembly of `libgssIpcRteHmiProxy.so` identifies vtable `0x53d70`:

- Slot 0 at `0x3d47c`: `str r1,[r0,#4]`; `bx lr`. This stores the callback receiver in object field `+4`.
- Slot 1 at `0x40b80`: 180-case incoming dispatch, index 127 at `0x40ea4` routes to `0x43968`, which calls receiver vtable offset `0x70` at `0x43b5c`.
- Slot 2 at `0x3d77c`: independent 180-case dispatch, `cmp r1,#179` at `0x3d794`, table at `0x3d7a0`.
- Slot 3 at `0x3d484`: reads `[r0+4]` and invokes receiver method offset `0x230` or `0x234`, according to the second argument.

In the slot-2 table, index 127 is entry `0x3d99c`, jumping to `0x3e1cc`. There `mov r12,#127` followed by `strh r12,[sp,#230]` writes the ID as a 16-bit field. The handler calls helper `0x40a8`, then `0x3e2c`, consistent with constructing and forwarding a message. Exact transport semantics remain unverified. Index 177 in the same table is `0x3da64 -> 0x3fd18`, whereas the incoming table's index 177 is `0x40f6c -> 0x4fd34`.

This establishes a setter and two independent index-based dispatch methods in the proxy. It does not yet prove that the receiver object is the GTF2 vtable `0x88e6b8` or establish on-wire framing.