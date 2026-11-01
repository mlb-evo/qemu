# GTF2 DPInitDone writes a boolean DP

Original Stage2.1 `bin/gtf2`, SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

Verified with ARM disassembly: `0x12dd10` loads byte `manager+0x18c`; `0x12dd18` loads DP-ID `0x0200010e`; `0x12dd1c` calls `0x131534`. At `0x131534`, the value and DP-ID are preserved and the function references diagnostic `writeBool(0x%x, %i)` (literal at `0x7c41ba`). It tail-calls `0x1314b8` at `0x131580`; that function calls typed datapool operation `0x69ea0c` at `0x1314f0`. `0x69ea0c` checks element type through `0x69e510` and branches to `0x69e968` or `0x69e8c4`; unsupported type returns 3.

**Contract:** On first `eSIDThreadManDPInitDone` (selector `0x2af9`), GTF2 attempts `writeBool(0x0200010e, config[2])`, before setting `dp_done=1`. The caller does not check the write result, so success is not guaranteed. This resolves the earlier unknown classification in `gtf2-dp-init-side-effects.md`.

The producer of `0x2af9` is still unknown. Raw full-word little-endian search finds no `0x2af9` literal in executable, which is inconclusive because ARM can synthesize constants or use indirect construction. No Stage3 process work is in scope.
