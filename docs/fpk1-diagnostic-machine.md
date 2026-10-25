# FPK1 diagnostic QEMU machine

This is an **experimental machine skeleton**, not a working FPK1 emulator.
It instantiates the existing `Tegra30State`, maps 256 KiB IRAM at
`0x40000000` and DRAM at `0x80000000`, and starts the AVP with an
**explicitly supplied** entry address. It does **not** reconstruct FPK1
BootROM, BCT, NOR, Quickboot, board peripherals, display or QNX service
startup. In particular, the MHI2 BootROM handoff must not be treated as
FPK1 data.

Build as for the existing QEMU ARM target. After building, check:

```sh
./build/qemu-system-arm -machine help | grep fpk1
./build/qemu-system-arm -machine fpk1 -display none
# Expected: missing load=... diagnostic (before any guest boot).
```

A diagnostic raw image may be loaded **only** into DRAM. Both its physical
address and entry PC are mandatory; entry must be aligned and within the
loaded image. Example syntax (addresses are placeholders, not discoveries):

```sh
./build/qemu-system-arm -machine fpk1,load=0x80010000,entry=0x80010000 \
  -m 512M -bios /path/to/validated-raw-arm-test-image.bin \
  -nographic -d guest_errors,unimp -D fpk1-qemu.log
```

Do **not** pass `stage1_ifs.img` (the signed update component), its
HSP-stripped data or `qb_primary.img` directly as the test image: their
actual executable entry, relocation/handoff and startup context are unknown.
A successfully instantiated QEMU machine is not proof of working QNX.

## Research requirements

See [firmware research](fpk1-firmware-research.md). Next steps:
1. Validate Stage1 startup and its actual load/entry address.
2. Establish flash layout and FPK1-specific boot handoff (BCT/IRAM/AVP).
3. Add necessary board peripherals based on trace evidence.
4. Only then attempt original `procnto` startup and application services.

The profile deliberately does not modify `mhi2-harman` behavior.

## Firmware-free smoke test

The existing `.github/workflows/mhi2-build.yml` now calls
`python3 tools/fpk1/check_machine.py --qemu <path-to-qemu-system-arm>`
immediately after building QEMU. This reuses the already running Linux/macOS
ARM build job rather than adding a second expensive build.

The smoke test checks:
- `fpk1` appears in `-machine help`;
- missing mandatory addresses result in a nonzero exit;
- an entry point outside a four-byte image is rejected;
- a generated, non-proprietary ARM A32 branch-to-self binary starts without
  an immediate fatal error (the test terminates it by a two-second timeout).

These are **machine initialization** checks, not proof of executing FPK1
firmware or booting QNX. This PR has not yet passed a QEMU compile/run
in the current environment; rely on the existing CI once it executes.

## Verified decoded primary Stage1 experiment

The primary Stage1 ZV/LZF stream can now be decoded with matching CRC32 and QNX
startup/imagefs checksums. Use `tools/fpk1/probe_stage1_startup.py` for bounded
experiments; it handles temporary decoded bytes and deletes them afterward.
The header-consistent stub load/PC is `0x80a00800`, branching to `0x80a06b98`.
This applies to the **decoded** image, not the signed component or raw payload.

The existing diagnostic machine executes startup but reaches a Data Abort
(DFAR `0x3`). A command-line CBAR override moves progress to another Data Abort
(DFAR `0xff7`); neither experiment boots QNX. See the latest complete Stage1
section in [firmware research](fpk1-firmware-research.md) for commands and evidence.
