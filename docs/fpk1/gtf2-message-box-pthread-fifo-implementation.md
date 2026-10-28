# GTF2 named message boxes: in-process pthread FIFO

Verified against original stock `gtf2` SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This resolves the transport ambiguity in `gtf2-threadman-named-message-box.md`.

The channel named `/eMsgBoxIDThreadManager` (index 3) is implemented in the process by linked heap nodes, a mutex and a condition variable. It is **not** a POSIX `mq_open` endpoint. ARM PLT imports were resolved through original ELF relocation and symbol tables.

| Function | Relevant PLT imports | Key operations |
|---|---|---|
| `0x68d060` send | `malloc` `0x10e7ec`; `memcpy` `0x10dbd4`; `pthread_mutex_lock` `0x10dcdc`; `pthread_cond_signal` `0x10f140`; `pthread_mutex_unlock` `0x10d808` | Allocates `length+8` node, stores next=0 and length, copies payload to node+8, checks capacity, appends FIFO node, increments count, signals waiter |
| `0x68cf00` receive | `pthread_mutex_lock` `0x10dcdc`; `pthread_cond_wait` `0x10dcf4`; `pthread_mutex_unlock` `0x10d808`; `memcpy` `0x10dbd4`; `free` `0x10e2c4` | Waits while empty, checks destination buffer length, removes head, decrements count, copies payload, frees node, returns message length |
| `0x68d308` create | `strlen` `0x10edd4`; `strcmp` `0x10f1e8`; `strcpy` `0x10d88c` | Maintains local named-slot table |

Machine-code anchors: `0x68d0a0` malloc; `0x68d0d8` node header; `0x68d0e0` memcpy; `0x68d0e8` mutex lock; `0x68d1a0` append tail; `0x68d1a8` set head if empty; `0x68d1d4` cond signal; `0x68d1f0` count increment; `0x68d1f4` mutex unlock. Receiver `0x68cf44` lock; `0x68cf98` cond wait; `0x68cfd0` read node length; `0x68cfd4` capacity compare; `0x68cff8` advance head; `0x68d01c` decrement count; `0x68d020` unlock; `0x68d030` copy; `0x68d038` free.

Static end-to-end: callback vtable slot 136 `0x693ff0` sends selector `0x2afa` to channel index 3 -> `/eMsgBoxIDThreadManager` -> bounded pthread FIFO -> ThreadMan `0x69b29c` receives from same index 3 -> `0x12dfb0` dispatches `eSIDThreadManRTEUpdateDone` -> DP guard checks -> delayed/Stage3/immediate HMI startup.

**Not yet established:** external ASI `IHmiKss` method name for slot 136, actual runtime callback timing or successful delivery. The internal message-box channel and external ASI IPC are separate mechanisms.

Reproduce with `tools/fpk1/research/gtf2/disassemble_ptload.py` ranges `0x68d060..0x68d200`, `0x68cf00..0x68d050`, and `0x68d308..0x68d4c4`.