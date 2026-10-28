# ThreadMan RTEUpdateDone producer and consumer select the same internal channel index 3

Binary: stock `gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This resolves the channel-index ambiguity left in `gtf2-threadman-message-send-receive.md`. It does **not** resolve the unrelated external `IHmiKss` method number.

## End-to-end register/field proof

The RTE callback at vtable slot 136, `0x693ff0`, sets `r1=3` and `r2=0x2afa` before `0x12ca9c`:

```asm
693ff4 movw r2,#0x2afa
693ff8 mov  r1,#3
693ffc mov  r0,sp
694000 bl   0x12ca9c
```

`0x12ca9c` forwards the channel index in `r0` and selector in `r1` to `0x69b6b8` (`0x12caa8..0x12cab8`). In `0x69b6b8`, `r6` holds that channel index and `r5` holds the selector. The message initializer `0x6abce8` is called with `r3=r6` and fifth stack argument `r5`. Its instructions **`0x6abcfc STR r3,[r0]`** and **`0x6abd00 MOV r1,lr`** establish the channel index in message field `+0` and selector in the message construction path. It also stores payload pointer at `+4`, capacity at `+8`, length at `+0xa`, and active flag at `+0xd`.

Sender `0x69b4ac`:
```asm
69b4b8 bl 0x68d7f8      ; initialize shared channel array if needed
69b4bc ldr r1,[r4]      ; r1 = message.channel_index = 3
69b4c0 bl 0x68d570      ; descriptor = table[r1]
69b4c4 ldrh r2,[r4,#10] ; message length
69b4c8 ldr r1,[r4,#4]   ; message payload
69b4d0 bl 0x68d060      ; send-side transport helper
```

The shared accessor `0x68d570` is exactly `LDR r0,[r0,r1,LSL #2]; BX lr`. The singleton accessor `0x68d7f8` returns a pointer to the shared array at `0xdb0bf4` (literal `0x68d848`), initializing it through `0x68d5b0` once.

Receiver `0x12e0a8`:
```asm
12e108 mov r0,#3
12e110 beq 0x12e0cc
12e11c beq 0x12e0cc
12e0cc bl 0x69b29c
```
At `0x69b29c`, `r4=r0` saves **3**; it calls the **same** `0x68d7f8` and passes `r1=r4` to the **same** `0x68d570` at `0x69b2ac..0x69b2b0`. Thus both sides select **table[3]**, with the same singleton array and accessor, before send/receive helper calls. The receiver subsequently uses `0x68cf00` with a 64-byte destination buffer.

This proves **same internal channel-table index and shared descriptor slot**, stronger than the earlier observation of shared helper names. It does not prove that an individual message was successfully delivered at runtime, or whether send/receive use the same underlying OS descriptor integer rather than distinct endpoints within that slot; inspect `0x68d5b0` and the channel descriptors for that detail.

## Scope / nonclaims

- Index **3** is an **internal message-channel selector**, not the external `IHmiKss` method ID and not callback slot 136.
- `0x2afa` is the **ThreadMan message selector**, not a channel number.
- Callback table slot **136** identifies the local implementation `0x693ff0`, not a wire protocol method ID.
- No runtime delivery or external ASI registration sequence is inferred from static code.

## Reproduce

```sh
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x693ff0 --stop 0x69401c
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b6b8 --stop 0x69b6f0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x6abce8 --stop 0x6abd24
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b4ac --stop 0x69b4d8
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x69b29c --stop 0x69b2c0
python3 tools/fpk1/research/gtf2/disassemble_ptload.py /path/to/gtf2 --start 0x68d7f8 --stop 0x68d850
```
