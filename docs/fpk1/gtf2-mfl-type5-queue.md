## Synthetic MFL type-5 record reaches aggregate queue (stock ELF)

Disassembly verifies aggregate constructor `0x15151c` stores vtable pointer `0x7c9030` at aggregate+0. That vtable's slot 0 points to `0x150938` (slots 1 and 2: `0x15105c`, `0x151028`). Thus the virtual slot-0 call in `0x14ea10` is statically resolved: `0x18930c -> 0x14ea10 -> 0x151558 (singleton aggregate) -> [vptr+0] = 0x150938`.

`0x150938` does not synchronously deliver the type-5 record to an HMI scene. It allocates a 24-byte node with `0x10e384(24,...)`, initializes its embedded record through `0x154598(node+12, record)`, and links the node to a list rooted at the aggregate backing object (`aggregate+4`): loads tail pointer `[backing+0x24]`, sets `[node+4]=backing+0x1c`, `[node+8]=old_tail`, stores `[old_tail+4]=node`, then stores `[backing+0x24]=node` (`0x1509ac..0x1509c4`). Calls `0x150920(backing+8)` afterward, likely to signal work; the precise behavior of `0x10f140` and `0x10d868` inside `0x150920` needs further tracing. This establishes **queue insertion, not direct UI update**.

`0x151558` lazily initializes a global singleton at address `0xab6878`: it allocates 8 bytes, calls `0x15151c` to set vtable and create backing object via `0x151088`, stores singleton pointer in `[0xab6878]`, and returns it. The generated type-5 record's concrete first consumer is therefore a queued work item, with actual dequeue/dispatch still unresolved.

All findings from static ARM32 disassembly of stock GTF2; no QEMU execution.
