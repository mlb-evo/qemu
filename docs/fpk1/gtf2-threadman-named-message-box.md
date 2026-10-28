# ThreadMan message channel resolved to named /eMsgBoxIDThreadManager

Stock GTF2 SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This consolidates the message transport reconstruction across `gtf2-threadman-channel-index-proof.md`, `gtf2-threadman-message-send-receive.md`, and `gtf2-rte-completion-callback-slot.md`. **New evidence:** names, descriptor initialization, index-to-name mapping, and implementation characteristics of the message-box mechanism.

## Four named message boxes, initialized in exact index order

The singleton initializer `0x68d7f8` calls `0x68d5b0` with the four-word array at `0xdb0bf4`. In `0x68d5b0`, four sequential calls to `0x68d308` store returned descriptors at `[r4+0]`, `[r4+4]`, `[r4+8]`, `[r4+12]`. Their name pointers are literal loads immediately before the calls.

| Index | Descriptor store | Name pointer literal | String VA | Exact stock name | Creation call |
|---|---|---|---|---|---|
| 0 | `0x68d5f0 STR r0,[r4]` | `0x68d7c4` | `0x88cdbd` | `/eMsgBoxIDGui` | `0x68d5e8 BL 0x68d308` |
| 1 | `0x68d670 STR r0,[r4,#4]` | `0x68d7e0` | `0x88ce6a` | `/eMsgBoxIDDatapool` | `0x68d668 BL 0x68d308` |
| 2 | `0x68d6f0 STR r0,[r4,#8]` | `0x68d7e8` | `0x88cea6` | `/eMsgBoxIDApplication` | `0x68d6e8 BL 0x68d308` |
| 3 | `0x68d770 STR r0,[r4,#12]` | `0x68d7f0` | `0x88ceee` | **`/eMsgBoxIDThreadManager`** | `0x68d768 BL 0x68d308` |

All four calls use `r1=0x102` and `r2=0x1ff` (ARM MOVW opcodes), with a temporary attribute block setting max message count 64 and message size 64 for index 0, and message count 16 / size 64 for indices 1–3. These values are initializer arguments, not observed runtime queue depth.

Each failure branch logs an explicit stock string, respectively `Failure in creating message queue for HMI`, `... for DP`, `... for Application`, `... for Thread Manager`.

## Transport proof: same *named* channel, not merely similar helpers

```text
IHmiKss callback table slot 136 -> 0x693ff0
  -> message constructor (channel_index = 3, selector = 0x2afa)
  -> 0x12c994 -> 0x69b4ac
  -> 0x68d7f8 (singleton) -> 0x68d570(table,3)
  -> table[3] == descriptor created for /eMsgBoxIDThreadManager
  -> 0x68d060 (send helper)

ThreadMan run 0x12e380 -> 0x12e0a8 (r0=3)
  -> 0x69b29c
  -> 0x68d7f8 (same singleton) -> 0x68d570(table,3)
  -> table[3] == descriptor created for /eMsgBoxIDThreadManager
  -> 0x68cf00 (receive helper, 64-byte buffer)
  -> selector 0x2afa -> 0x12dfb0
  -> 0x13076c -> DP guards -> conditional Stage3/HMI startup
```

This is a **complete static join at the same named message-box descriptor**. The actual runtime scheduling, success/failure, and external `IHmiKss` wire method remain unproven.

## Implementation detail and caution about POSIX interpretation

The name strings have a POSIX-like leading slash, and stock error text uses “message queue” and references `mq_overview`. But `0x68d308` is a substantial application-level helper: it checks `strlen`, loops over eight named slots using `strcmp`, allocates and initializes internal state, and calls `pthread_cond_init` via PLT `0x10dad8`. `0x68d060` likewise contains custom allocation and shared-state checks. **Do not assert these are OS `mq_open` descriptors solely from the names**. Resolve the underlying helper implementation and imports before assigning an OS transport type.

The fourth channel is unequivocally named `/eMsgBoxIDThreadManager`; the three others are separate internal message boxes and must not be conflated with ASI `IHmiKss` interface names.

## Reproduction on original ELF

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d5b0 --stop 0x68d7f8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d7f8 --stop 0x68d850
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d308 --stop 0x68d4c4
```

Extract literal values from original executable PT_LOAD with `struct.unpack_from('<I', blob, va - 0x100000)`; decode strings at the four virtual addresses above. The executable image contains original program bytes and no synthetic instructions.

## Remaining external boundary

The internal completion-event path is statically closed up to named channel and event dispatcher. Next high-value task is the **external `IHmiKss` descriptor/method mapping for vtable slot 136**. The vtable index, ThreadMan selector `0x2afa`, and message-box index 3 are three different number spaces; none is an ASI method number.
