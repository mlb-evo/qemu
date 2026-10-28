## Proxy-side virtual slot 28 call sites (stock firmware)

Extracted actual `lib/factories/libgssIpcRteHmiProxy.so` (348160 bytes) from `STAGE2.1` of the firmware ZIP. The ELF has no section headers but PT_LOAD disassembles with llvm-objdump.

Two instruction sequences use callback virtual slot offset 0x70 (index 28): at proxy `0x1ed2c..0x1ed44`, `ldr r3,[r4,#4]; ... ldr r3,[r3]; ldr r3,[r3,#0x70]`, with callback receiver r0=[r4+4], r1=byte at stack+0x5ef, r2=stack+8, and tail branch to `0x1c9b0`. At proxy `0x43b3c..0x43b5c`, `ldr r3,[r5,#4]; ... ldr r3,[r3]; ldr r3,[r3,#0x70]; blx r3`, with r0=[r5+4], r1=stack+0x1350 (calculated from 4864+32-8). The first call also sets up an indirect invocation through 0x1c9b0; its precise ABI and callback object class still need to be resolved.

**Critical caution:** an offset of 0x70 is NOT a globally unique IPC method identity. It denotes virtual slot 28 of whatever dynamic class is stored at `[r4+4]` or `[r5+4]`. To equate either call with GTF2 `0x696f4c` one must show that the callback pointer installed by GTF2 `0x6977a4` reaches the respective proxy object field, and that its vptr is GTF2 `0x88e6b8`. The proxy call at 0x43b58 is a concrete indirect invocation, but the 0x1ed40 path may be a different interface and the presence of two call sites makes the identity problem nontrivial. This file documents **candidate call sites**, not a confirmed source-method mapping.

Next: trace proxy callback registration setters and the owning dispatch selector/decoder for 0x43b3c and 0x1ed2c, then compare the marshalled argument wrapper with the 0x696f4c payload dereference `[r1+4]`.
