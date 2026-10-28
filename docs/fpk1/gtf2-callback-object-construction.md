# Stock ELF: callback table object construction and first caller

Source: original `STAGE2.1/bin/gtf2` (SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`). This is an extension of `gtf2-callback-pointer-table.md`, based on decoding actual ARM instructions and direct BL references.

## Exact construction chain

`0x68eeb4 BL 0x69780c` in the function beginning `0x68ee80`. This is a direct call, not an inferred association from proximity.

`0x69780c`:
- `0x697814 MOV r0,#0x34`; `0x69781c BL 0x10dcac` allocates a 52-byte object (allocator behavior inferred from usage; direct call and allocation size are observed).
- `0x697820 MOV r1,r6`; `0x697824 MOV r5,r0`; `0x697828 BL 0x6977a4` initializes the allocated object using the passed argument.
- `0x69782c MOV r0,r4`; `0x697830 MOV r1,r5`; `0x697834 LDR r2,[pc,#0xc]` loads the literal `0x68dbe4` from `0x697848`; `0x697838 MOV r3,#0`; `0x69783c BL 0x10eb7c`. **Do not label this IPC registration yet**: the function might be an ownership/container assignment helper. The call and arguments are the evidence.

`0x6977a4`:
- Stores incoming `r1` at object `+0xc` and incoming `r2` at `+0x8` (instructions `0x6977b8` and `0x6977bc`).
- `0x6977cc BL 0x6998f4` and `0x6977d4 BL 0x10edb0` initialize subobjects.
- Loads `0x88e6b0` from literal `0x697800`; `0x6977e8 STR r2,[r4,#0x24]` writes a derived table pointer to object `+0x24`. `0x6977ec STR r3,[r4,#0x1c]` writes the other table pointer (derived from literal `0x88e360`) to `+0x1c`.
- `0x6977f4 BL 0x10e1a4` is another helper, not yet classified.

The earlier `0x693804` and `0x693884` functions likewise embed `0x88e6b0`, but they are **not proven to be invoked by the above construction path**. Direct BL scans find one caller of `0x6977a4` (`0x697828`), one caller of `0x69780c` (`0x68eeb4`), and no direct BL callers of `0x693804`/`0x693884` in the scanned executable range. This is consistent with other entry paths (including virtual calls), not proof of them.

## Next proof gap

At `0x68ee80` the code also calls `0x693294` at `0x68ee98` and `0x6921cc` at `0x68eea4` before constructing the object. Determine the semantic role of the caller and trace what happens to the object initialized at `0x6977a4`. A constructor storing a vtable pointer is not evidence of a live IPC subscription.

No IAA design or protocol naming is inferred here.
