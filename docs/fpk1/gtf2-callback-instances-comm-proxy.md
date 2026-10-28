# HmiComm callback instances connect to a comm::Proxy constructor

Verified in stock GTF2 ELF (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`) by disassembling executable PT_LOAD and resolving PLT entries through original ELF `R_ARM_JUMP_SLOT` relocations. Builds on `gtf2-hmicomm-two-callback-instances.md` and does not re-claim discovery of the callback vtable.

## Per-instance processing after construction

`0x68ee80` first creates two `0x69780c` callback objects with instance arguments 1 and 2 and stores them in the owner vector. Later it iterates that vector:

```asm
68f31c ldr r3,[r5]
68f320 ldr r6,[r3,#8]    ; vector end
68f328 ldr r0,[r6,#-8]   ; current shared-pointer's object
68f32c bl 0x697e94
68f330 ldr r3,[r5]
68f338 add r6,r6,#12     ; 12-byte vector entry
68f33c ldmib r3,{r0,r2}  ; vector start/end metadata
68f348 bne 0x68f328
```

`0x697e94` requires non-null object fields `+0x28` and `+0x2c`, reads the stored per-instance value at `+0xc` (`0x697ee0`), and passes it along with the object pointer and associated shared-pointer record into `0x6939b4` at `0x697f1c`. The call `0x697d04` prepares object-related state before that operation. **This is a per-instance setup/activation path, not simply object construction.**

## Dynamic-symbol resolution identifies communication library boundary

Within `0x6939b4`, a 108-byte object is allocated (`0x693be4`), initialized (`0x693c00`), and passed to `0x10ebe8` at `0x693cd0`. The imported symbol is exactly:

```cpp
comm::Proxy::Proxy(
    comm::TrackedBase::IdentityArgs const&,
    comm::ServiceRegistration const&,
    comm::InterfaceStyle,
    comm::LifecycleListener*)
```

ELF evidence: PLT `0x10ebe8` maps to GOT `0xa6577c`; `R_ARM_JUMP_SLOT` relocation index 434, dynamic symbol index 572, mangled name `_ZN4comm5ProxyC2ERKNS_11TrackedBase12IdentityArgsERKNS_19ServiceRegistrationENS_14InterfaceStyleEPNS_17LifecycleListenerE`.

Other relevant resolved imports:

| PLT VA | Dynamic symbol |
|---|---|
| `0x10e27c` | `comm::LifecycleImpl::LifecycleImpl(comm::Lifecycle::State, comm::LifecycleListener*)` |
| `0x10df10` | `ipl::UUID::UUID(ipl::UUID const&)` |
| `0x10e21c` | `util::SharedPtrDefaultBase::SharedPtrDefaultBase(util::SharedPtrDefaultBase const&)` |
| `0x10e468` | `atomic_add_value` |

This is the first identified **`comm::Proxy` constructor** in the per-instance callback setup chain. It supplies a concrete place to recover `ServiceRegistration`, interface UUID and lifecycle semantics. Do not call the constructor itself a successful external subscription.

## Relationship to ThreadMan RTEUpdateDone

The existing callback vtable `0x88e6b8` contains slot 136 -> `0x693ff0`, which sends `0x2afa` through the process-local `/eMsgBoxIDThreadManager` pthread FIFO. Both instances share the table. The `comm::Proxy` setup is **upstream infrastructure** but does not yet establish the external method ID, which instance receives the call, or exact method dispatch mapping.

## Next proof targets

1. Decode `ServiceRegistration` argument and interface UUID supplied to `comm::Proxy`.
2. Find the actual dispatch path from `comm::Proxy`/interface object to callback slot 136.
3. Determine whether `0x693ff0` is a lifecycle notification rather than a wire-method callback. Its position in the large vtable alone cannot distinguish these.
