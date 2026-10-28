# GTF2 HMI channel-0 dispatch: 13 indexed handlers

Source: original Stage2.1 `bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. Original ARM disassembly.

`0x11459c` receives channel-0 message with `0x69b29c(0)` and passes it to `0x12c008(context+27312, context, message)`.

At `0x12c008`, r0 is a pointer to a handler-pointer array, r1 is HMI context, r2 is the message. It initializes an 88-byte local frame and calls `0x69b45c(message)` at `0x12c038`, retaining its returned selector in r6.

At `0x12c090`, it computes `uint16_t(selector - 1)` and checks <=12. If in range, `0x12c09c` loads the handler from `[table + selector*4]`; otherwise `0x12c0a0` loads fallback handler from `[table+0x38]`. It skips a null handler. If nonnull, `0x12c0ac–0x12c0c0` obtains the first virtual method of the handler object and invokes it with message, temporary context and HMI context. Afterward `0x6aa3ac` and optionally `0x6aa204` perform post-dispatch work.

**Meaning:** the HMI worker has an explicit indexed **message dispatcher** for selector values 1..13, plus fallback slot at index 14. It is NOT the same dispatcher as the channel-3 `0x12dfb0` two-event barrier. The selector's semantic names and handler pointer initialization must still be mapped. Do not conflate these selectors with DP-IDs, external IPC method slots or `0x2af9/0x2afa`.

Next: map the handler array built in `0x114650` (`0x12bfcc` registrations at selector IDs 2,3,4,8,7,5,6,11,10,12), then identify concrete virtual handler targets and their state/scene effects.
