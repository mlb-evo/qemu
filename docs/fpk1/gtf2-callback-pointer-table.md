# New evidence: 12 unresolved DP writers appear in one stock ARM function-pointer table

Source: extracted original `STAGE2.1/bin/gtf2` (10,180,269 bytes; SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`). This investigation is distinct from the earlier nearest-prologue/name recovery: it scans **literal 32-bit references to the candidate function entrypoints** in the binary.

## Direct observations

- At VA `0x88e6b0` and `0x88e6b4`, two 32-bit words are zero. Beginning at `0x88e6b8` is a contiguous array of **148 function-like 32-bit addresses** through `0x88e904` inclusive. The next word at `0x88e908` is `0xfffffffc`, followed by zero at `0x88e90c`, consistent with a new adjacent table or secondary layout. **The function-pointer array extent is a structural hypothesis** until the ABI layout is independently verified.
- Each of the 12 previously unresolved DP write functions has an **exact pointer entry** in this array. No approximate address or string-name match is required. See `gtf2-unresolved-callback-pointer-slots.csv` for every pointer VA and index (zero-based relative to `0x88e6b8`).
- The table **base pointer `0x88e6b0`** appears as a literal at code VAs `0x693864`, `0x6938dc`, and `0x697800`. For example, ARM `LDR r3, [pc, #0x54]` at `0x693808` loads the first literal at `0x693864`, whose value is `0x88e6b0`. The surrounding code at `0x693818` and `0x693824` writes derived pointers to an object rooted at `r4` (the incoming `r0`); this is **object initialization evidence** rather than merely a detached static address table.
- The table contains many other callback-like functions, so these 12 are **not isolated unknown functions**. The slot index supplies a concrete path for the next phase: identify the interface object and its dispatch machinery.

## Important limitations

- This **does not yet prove** that the table is the primary `IHmiKss` virtual method table, nor that the slot order is the IPC wire method order. Do not name the slots or infer a protocol method number from the index.
- The ARM function entrypoints are still identified using the earlier nearest-prologue heuristic; the new contribution is their **independent literal-pointer reference**.
- The array has a pair of leading zero words, but the object's vptr is observed as `0x88e6b0`, not automatically as `0x88e6b8`. It is premature to impose an Itanium ABI `vptr + 8` convention.
- This table alone does not establish where the IPC subscription occurs, how `gss_ipc` dispatches messages, or how the DP values reach Kanzi.
- No firmware binaries or raw proprietary assets are committed.

## Follow-up target

Trace the object initialized at `0x693804` / `0x6977a4`, identify the code that receives or registers its pointer, and correlate the table with `asi.gss.ipc.rte.hmi.IHmiKss` and the `IHmiKssReply` descriptor. Only then can the slot index be interpreted as a confirmed callback mapping.
