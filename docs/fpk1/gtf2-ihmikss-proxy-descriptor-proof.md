# IHmiKss descriptor in per-instance proxy setup

Original stock `gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

The `0x6939b4` setup routine called from `0x697e94` for each of the two callback objects uses the actual `IHmiKss` and `IHmiKssReply` interface descriptors.

| Address | Value | Interpretation |
|---|---|---|
| `0x693d30` | `0xa7f838` | descriptor pointer loaded at `0x693ab0` |
| `0xa7f838` | `0x88f55d` | exact string `asi.gss.ipc.rte.hmi.IHmiKss` |
| `0x693d44` | `0xa7f83c` | descriptor pointer loaded at `0x693bb0` |
| `0xa7f83c` | `0x88f579` | exact string `asi.gss.ipc.rte.hmi.IHmiKssReply` |

The first string pointer is dereferenced at `0x693ac8` and stored in a stack-local registration structure at `0x693b08`. The second is dereferenced at `0x693bc0` and stored at `0x693bc4`. The same routine invokes `comm::Proxy::Proxy` through PLT `0x10ebe8` at `0x693cd0`.

Proven chain: `HmiComm 0x68ee80` -> two callback instances via `0x69780c` -> per-instance setup `0x697e94` -> `0x6939b4` -> `IHmiKss/IHmiKssReply` descriptor construction and `comm::Proxy`.

This proves interface identity, **not** external wire-method identity. Callback vtable slot 136 (`0x693ff0`) still has no verified external ASI method ID or name, and runtime invocation timing is unknown. The vtable slot index 136, ThreadMan selector `0x2afa`, and internal message-box index 3 are separate numbering spaces.

Reproduce using `tools/fpk1/research/gtf2/disassemble_ptload.py` ranges `0x693ab0..0x693bd0` and `0x693ca8..0x693cd4`, and inspect the four ELF addresses listed above.