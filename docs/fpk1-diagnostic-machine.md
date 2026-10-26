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

## Synthetic CPU0 and memory handoff

The default AVP profile remains the baseline. To reproduce the measured entry
into `procnto`, opt into CPU0 and supply the memory description expected by the
BSP. The probe changes per-run QOM reset properties and loads synthetic ATAGs;
it does not change this machine's default or patch the firmware.

```sh
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --boot-cpu cpu0 --memory-handoff \
  --tcg-thread single --run-ms 2000 --json /tmp/fpk1-kernel-handoff.json
```

The exact kernel entry `0xfe054a58` is traced, and CPU0/CPU1 are sampled inside
kernel code without the earlier Data Aborts. The console remains empty; running
startup-script commands and services is still unverified. These are synthetic
handoff experiments, not a reconstruction of the real FPK1 bootloader.


The corrected ARM64 CSSC backend and an explicit instruction-count clock now
allow matching execution of early startup.script programs, including
sifsloader. For this newer bounded profile use `--kernel-state --icount-shift 0
--trace-limit-kib 8192` in addition to the CPU0/memory/single-TCG options above.
See the firmware research notes for byte-level entry evidence and the distinction
between program entry and service readiness. The independent regression is:

```sh
python3 tools/fpk1/check_tcg_shifts.py --qemu ./build-fpk1/qemu-system-arm
```

## Board identity, eMMC and Stage3

The machine accepts an optional eMMC on SDMMC4 via
`-drive if=sd,index=0,format=raw,file=...` (absent by default). With the
synthetic Quickboot-style command line (`nvsku=699-61852-0005-200 ...`) and an
eMMC assembled from the update archive, the original scripts boot through
Stage2 to the Stage3 fallback; gtf2 fails at the unemulated NVIDIA graphics.

```sh
python3 tools/fpk1/create_fpk1_emmc.py <firmware.zip> /tmp/fpk1-emmc.img
python3 tools/fpk1/run_stage1_console.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --icount-shift 0 --board-info \
  --emmc /tmp/fpk1-emmc.img --seconds 240 --json /tmp/fpk1-console.json
```

See "Bootloader command line, eMMC and boot to Stage3" in the
[firmware research](fpk1-firmware-research.md) for evidence and limits.

## Quick start: build once, then `run.sh`

Like MHI2's `build_audi.py`, `tools/fpk1/build_fpk1.py` prepares a new
directory with everything needed to watch FPK1 boot:

```sh
python3 tools/fpk1/build_fpk1.py \
  --archive /path/to/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip \
  --output "$PWD/../fpk1-build"        # add --qemu build-fpk1/qemu-system-arm to reuse a build
bash ../fpk1-build/run.sh              # console in the terminal, frames in a window
bash ../fpk1-build/run.sh --headless   # no window; frames are still saved
```

The output holds `qemu/qemu-system-arm`, the GLES `bridge/` (guest shim and
`glhost`), `media/emmc.img`, a `venv/` with `lzokay` (sharing system PySide6)
and `build-manifest.json`. The archive is referenced, not copied; the output
directory must not exist. Each run writes logs, `result.json` and frames to
`runs/<time>/`. `run.sh` accepts `--seconds N` (default 1800) and any
`run_stage1_console.py` option; Ctrl-C stops it.

Requirements: `arm-none-eabi-gcc`, Mesa/NVIDIA EGL and GLES development files,
FFmpeg (`libavcodec-dev`, `libavutil-dev`, `libswscale-dev`), `liblzo2`,
`python3-venv` and, for the window, `python3-pyside6.qtcore`, `.qtgui` and
`.qtwidgets`. Building QEMU also needs `ninja-build` and the usual QEMU build
dependencies.

What to expect: Stage1/2 boot, then the Stage3 fallback after about 65 s;
roughly two minutes in, the viewer follows `grengme`'s service menu ("Main",
"Debugging", "GSS"). The cluster HMI (`gtf2`) does not draw, and the guest
display controller stays black: see the firmware research notes for why.
