# GTF2 worker lifecycle: launch before init barrier, stop after barrier

Evidence: original `bin/gtf2` ARM disassembly, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

## Registry callback mapping

`0x130074` stores first callback (`r1`) at descriptor `+0` and second (`r2`) at `+4`; `0x130100` copies both; `0x13019c` inserts the record into an ID-keyed tree. HMI ID 2 has first callback `0x68c860` and second `0x68c84c`.

`0x12ff70` looks up a record by ID and branches by third argument: if zero, it calls `0x12fec8`; if nonzero, it calls `0x12fc64`. `0x12fec8` enters `0x12fe04`, which uses the record's first callback at `+0` as a thread-start callback through `0x688e80` and stores the returned handle at `+0x18`. The lower-level API still needs symbol verification.

`0x12fdb4` looks up a record and calls `0x12fcec` with record base. `0x12fcec` calls `0x12fc30` (waits/cleans stored thread handle) and then executes `BLX [record+4]` at `0x12fd58`. For HMI ID 2, this is **`0x68c84c`**, not `0x68c860`. `0x68c84c` writes byte 1 to global `0xdb0858`; HMI worker `0x68c860` polls this byte at `0x68c8b0`, so the second callback is a **stop signal**.

## Actual ordering

Before the DP/RTE two-event barrier, `0x12e380` calls `0x12e124` at `0x12e3d8`. `0x12e124` calls `0x12ff70` for worker IDs **1 (DP)** and **2 (HMI)** with third argument 0, then configures message-box masks via `0x69b110(-1)` and `0x69b100(0xffff)`. If its configuration flag is true, it also invokes worker ID **0 (DP_COM)** with argument `0x2ee0` (12000), taking the nonzero branch.

Only after that does `0x12e380` enter the two-event barrier `0x12e0a8`. The HMI worker `0x68c860` can therefore execute `0x114650`, perform the eight-slot pass and send `DPInitDone` (`0x2af9`) while the main ThreadManager is waiting.

**Correction of prior research:** The post-barrier `0x12de74` sequence (3,4,5,2,1; optional 0) invokes `0x12fdb4`, which **waits/cleans worker handles and invokes their second callbacks**. It is not a deferred worker launch. In particular, the HMI secondary callback is the stop-flag setter. The post-barrier sequence should not be represented as startup of HMI.

## Open questions

Confirm whether `0x688e80` is pthread_create or a QNX thread wrapper and precise return/failure behavior. Determine why the main thread stops/joins the workers after both completion events and whether the code subsequently starts other services or enters the render loop via the final virtual calls. Runtime scheduling and thread completion are not proven from static call order alone.
