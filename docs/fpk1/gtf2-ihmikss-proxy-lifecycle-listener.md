# Distinguish primary IHmiKss callback dispatch from comm::Proxy LifecycleListener

Stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Direct original ELF disassembly and pointer reads. Extends `gtf2-ihmikss-proxy-descriptor-proof.md`, avoiding the previously repeated primary vtable discovery.

## The actual fifth constructor argument is the secondary subobject

At `0x697e94`, the two per-instance callback objects enter setup. The call to `0x6939b4` at `0x697f1c` passes `r0=sp+8`, `r1=object[+0xc]`, `r2=object`, `r3=sp+20`, **fifth argument `[sp]=object+4`** (`0x697f0c ADD r12,r4,#4`; `0x697f10 STR r12,[sp]`). The wrapper `0x6939b4` saves the incoming fifth argument, then at `0x693cb0 LDR lr,[sp,#0xd8]` and `0x693cc4 STR lr,[sp]` passes it unchanged as the fifth argument to imported `comm::Proxy::Proxy(IdentityArgs const&, ServiceRegistration const&, InterfaceStyle, LifecycleListener*)` at `0x693cd0`. The register `r3=0` at `0x693cac` is the fourth argument `InterfaceStyle`; `r2=sp+0x98` points to registration data.

In the constructor `0x6977a4`, `0x6977c8 STM r4,{r2,r3}` writes **primary vptr `0x88e6b8` to object+0**, **secondary vptr `0x88e910` to object+4**. Therefore the exact `LifecycleListener*` passed to `comm::Proxy` is **the secondary polymorphic subobject at object+4**, not the primary 148-entry method table.

## Secondary listener table and concrete re-entry

The secondary table at `0x88e910` contains four function pointers:

| Secondary slot | Pointer VA | Target | Verified behavior |
|---:|---|---|---|
| 0 | `0x88e910` | `0x69387c` | this-adjusting destructor thunk |
| 1 | `0x88e914` | `0x6937fc` | this-adjusting thunk to `0x693804` |
| 2 | `0x88e918` | `0x693774` | this-adjusting no-op thunk to `0x69377c` |
| **3** | **`0x88e91c`** | **`0x698014`** | subtracts 4 from `this`; jumps to `0x69801c` -> `0x697e94` |

ARM proof: `0x698014 SUB r0,r0,#4`; `0x698018 B 0x69801c`; `0x698044 MOV r0,r4`; `0x69804c B 0x697e94`. The intervening code `0x69801c..0x698044` includes a conditional logging call and preserves the object pointer.

**Meaning:** a method on the actual `LifecycleListener` interface can re-enter the per-instance proxy setup routine. This is a concrete lifecycle callback behavior. It does not establish which library lifecycle state causes the call, nor whether repeated calls create a new proxy or return early; `0x697e94` has guards at entry.

## Primary slot 136 is a different interface slot

The **primary** vtable `0x88e6b8` slot 136 (`0x88e8d8`) points to `0x693ff0`, which constructs `eSIDThreadManRTEUpdateDone` selector `0x2afa` on internal channel 3. It is **not** the `LifecycleListener` method at secondary slot 3, nor is primary slot 136 a proven external ASI wire method ID. The primary callback object's `this` at `+0` and secondary listener subobject at `+4` must not be conflated.

The data at `0x88e908` and `0x88e90c` are RTTI-related vtable header words (`-4`, zero); `0x88e910` is the actual secondary address point. A further subobject address point exists at `0x88e928` (object+8), also distinct.

## Updated topology

```text
IHmiKss callback object (two instances, instance IDs 1 and 2)
  +0  primary vptr 0x88e6b8
       slot 136 -> 0x693ff0 -> internal ThreadMan RTEUpdateDone
  +4  secondary vptr 0x88e910
       passed to comm::Proxy as LifecycleListener*
       secondary slot 3 -> 0x698014 -> 0x69801c -> 0x697e94
         -> 0x6939b4 -> comm::Proxy constructor
  +8  further vptr 0x88e928
  +0xc instance ID
```

This **resolves the direct lifecycle-listener-vs-primary-slot ambiguity**, but does not yet recover the external method descriptor/dispatch mapping for primary slot 136. Next examine `comm::Proxy` registration and how the library invokes primary vtable methods, especially whether slot 136 represents an inbound wire event or a completion callback from another proxy operation.

Reproduce: disassemble `0x6977a4..0x6977cc`, `0x697e94..0x697f20`, `0x693ca8..0x693cd4`, `0x698014..0x698050`; read 4-byte pointer values at `0x88e910..0x88e91c`.
