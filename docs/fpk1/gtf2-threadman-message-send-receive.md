# ThreadMan completion message transport: concrete send/receive bridge

Stock GTF2 ELF SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Extends `gtf2-rte-completion-callback-slot.md`; avoids repeating the already-established callback object, DP routing and Stage3 paths.

## Sender-side verified ARM calls

`0x693ff0` is callback table entry 136 at `0x88e8d8`, not an external IPC method number. It constructs selector `0x2afa` and invokes `0x12c994`. The exact implementation:

- `0x12c994`: reads message wrapper's active byte at `+4`; only when set, loads its pointer at `+0` and calls `0x69b4ac` (`0x12c9a8..0x12c9ac`). If send returns zero, executes error reporting via `0x10e714`; updates wrapper active byte based on result (`0x12c9d4..0x12c9e4`).
- `0x69b4ac`: checks message pointer nonnull; `0x69b4b8 BL 0x68d7f8`, `0x69b4c0 BL 0x68d570`; reads **message+0x0a as a 16-bit unsigned field** and message+4 as a pointer; passes them to `0x68d060` (`0x69b4c4..0x69b4d0`). Tests result against -1 and returns boolean success/failure (`0x69b4d4..0x69b534`).
- `0x12c9fc`: calls `0x69b280` on the wrapper's owned message pointer, then clears the pointer and active byte.

These are concrete send-side edges; exact wire layout remains unproven until `0x68d060` and the underlying QNX messaging import are resolved.

## Receiver-side verified ARM calls

`ThreadMan::run` `0x12e380` invokes the processing loop `0x12e0a8`, whose `0x12e0cc` calls `0x69b29c`. In `0x69b29c`:

- `0x69b2a8 BL 0x68d7f8`, `0x69b2b0 BL 0x68d570`: same pair as sender.
- `0x69b2bc BL 0x6abf20`: acquire message object; return null is a distinct error path.
- `0x69b2f8 BL 0x68cd70`, `0x69b348 BL 0x68ce1c`: receive/prepare operations, with error checking against -1.
- `0x69b35c BL 0x68cf00`: reads into the **message object +0x10** buffer with **r2=64** and r3=0. This establishes a fixed 64-byte receive-buffer bound for this call, not the length of every possible message.
- Successful loop then obtains selector from the returned object via `0x14e58c` / `0x14e59c` and invokes `0x12dfb0`.

This establishes a common application-owned messaging helper family on both sides. It does **not** yet prove the two calls refer to the same concrete endpoint/connection ID, or that the message is carried via ASI external IPC rather than an internal QNX message channel. The consumer is the internal ThreadMan selector dispatcher, not the external RTE callback table.

## Important semantic distinction

```
External RTE callback dispatch (method number still unknown)
    -> callback vtable slot 136 / 0x693ff0
    -> 0x12c994 -> 0x69b4ac -> 0x68d060 [send-side helper]
    ... transport/channel identity not yet resolved ...
ThreadMan run / 0x12e0a8
    -> 0x69b29c -> 0x68cf00 [64-byte receive buffer]
    -> 0x12dfb0 / 0x2afa
    -> delayed/Stage3/immediate HMI startup choice
```

A slot number in a C++ vtable is not an IPC method ID. No interface descriptor → slot 136 method-name correspondence is established yet. Further work should resolve the channel or connection IDs and callback descriptor rather than infer a method name from neighboring entries.

## Reproduction

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x12c994 --stop 0x12ca20
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b29c --stop 0x69b438
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b4ac --stop 0x69b550
```
