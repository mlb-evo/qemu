# GTF2 StageManager DP consumer tracing: 0x0200012D / 0x0200013A

Source: original ARM32 GTF2 ELF SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`, disassembly at `/mnt/data/gtf2-all.dis`. This continues `gtf2-stage-transition-dp-writes.md`.

## Important distinction: literal occurrences are not executable consumers

Full disassembly contains **21** occurrences of literal `0x0200012d` and **755** of `0x0200013a`. Most occur amid contiguous data words rather than directly PC-relative loads. Example `0x273b7c` (2D) and `0x273c14` (3A) sit in a dense generated table containing other DP IDs and constants. These are **not 21 and 755 proven code consumers**. Must reconstruct the generated table schema to map DP ID -> binding/property.

## Direct consumer of 0x0200012D

At `0x1b9020–0x1b9104`, PC-relative load `0x1b9058` obtains `0x0200012d` from `0x1b910c`, and passes it to `0x14c750` at `0x1b9064` with output buffer `sp+0x22`, then examines resulting signed halfword at `0x1b90b4`. Depending on other flags it calls `0x1b8fdc(object, 0|1)` at `0x1b90fc`. This is a concrete read/use path distinct from StageManager writer; semantics of `0x14c750` and `0x1b8fdc` need deeper identification before assigning a scene-property name.

## Direct consumer of 0x0200013A

Function `0x21da68–0x21dac4` checks its incoming selector r2 against `0x00e3` and `0x020b` (`0x21da68–0x21da78`). For either selector:

- `0x21da7c` loads DP ID `0x0200013a` from literal `0x21dac0`;
- `0x21da88` calls `0x69ec38(id, &signed_short, 0)` to read it;
- `0x21da8c–0x21da94` checks the returned 16-bit value;
- if nonzero, `0x21da98–0x21daa0` writes 1 to `0x0200013b` through `0x69e968`;
- if zero, `0x21dab0–0x21dab4` writes 0 to `0x0200013b` through `0x69e968`.

Thus a **verified consumer/derived-DP edge** is `0x0200013A -> 0x0200013B` (boolean nonzero normalization) when selector `0xE3` or `0x20B` reaches this handler. It is not proof that this handler actually ran at 18–19 s, nor that `0x0200013B` is the gauge-visibility property.

## Next tracing steps

1. Identify registration/caller for `0x21da68` and semantics of selector values 0xE3 and 0x20B.
2. Identify `0x1b8fdc` and its caller graph to determine which object reacts to `0x0200012d`.
3. Reconstruct generated tables containing 0x0200013A, particularly table structure around 0x273b7c/0x273c14, instead of counting constants as subscriptions.
4. Runtime trace DP 0x0200012D, 0x0200013A and 0x0200013B during 17–20s, with LR and values; compare to stage-0 transition.

No direct scene property names or exact blanking trigger have yet been established. No Stage3.
