# FPK1 firmware reverse-engineering notes

Status: preliminary research, **not a bootable FPK1 machine**. Source: user-supplied Audi Q7 2018 update archive `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip`. No proprietary firmware binaries committed.

## Current verified status

Primary Stage1 is now reconstructed from **58 independently decoded ZV/LZF
frames**, with matching CRC32, startup checksum and imagefs checksum. Its catalog
contains 47 regular files (43 ELF), including the kernel and startup script.
All 46 distinct DT_NEEDED names across Stage1/Stage2 have catalog basename
coverage. An opt-in CPU0 + synthetic memory-ATAG + single-thread TCG experiment now
traces the verified `procnto` entry and samples CPU0/CPU1 inside kernel code.
Console and service startup remain unproven; see
[CPU and memory handoff](#cpu-and-memory-handoff-procnto-entry-reached).
See [complete Stage1 reconstruction](#complete-stage1-zvlzf-reconstruction-and-startup-script)
for authoritative coordinates, identities and reproduction commands. Earlier
raw-header and unframed-suffix sections below are historical investigation;
their contradictory size fields and missing dependencies have been superseded.

## Platform evidence

Strings previously observed in Stage 1 include `startup-nvidia-tegra3-mm`, `devb-mmcsd-tegra3`, `tegra2_ge` and `fs-qnx6`. Stage 2 includes `qnx-arm-qcc-fpk1` and `RL_QNX_OS_650SP1_MMX2_17.52A`. These strongly suggest an ARMv7/Tegra 3 QNX 6.5 SP1 stack. String evidence is **not** proof that the existing MHI2 boot chain or peripherals are compatible.

Existing machine `hw/arm/mhi2_harman.c` instantiates `Tegra30State`, maps RAM at `0x80000000`, and resets AVP PC to `0x480e0000`. Those are MHI2 implementation details, **not established FPK1 addresses**.

## HSP/update wrapper

The researched `stage1_ifs_SignInfo.xml` reports `START-BYTE-FLASHDATA=186 (0xBA)`, `START-BYTE-SIGNATURE=58`, `SIGNATURE-SIZE=128`, and equal compressed/uncompressed lengths for Stage 1. Eight bytes `41 FF 44 FF 4F FF 44 FF` occur at `0xBA..0xC1`. The working extracted payload begins at `0xC2`, after these eight bytes. Keep **flash-data start** distinct from **candidate raw image start** until wrapper semantics are fully understood.

| Image | Candidate payload bytes after 0xC2 | QNX magic occurrences | ELF magic occurrences | imagefs strings |
| --- | ---: | ---: | ---: | ---: |
| stage1_ifs.img | 2,060,288 | 1 | 41 | 2 |
| stage1_RECOVERY_ifs.img | 8,742,912 | 0 | 0 | 0 |
| stage2_ifs.img | 23,056,384 | 0 | 40 | 2 |

Magic/strings counts do not establish valid object boundaries. The `0x00ff7eeb` QNX startup signature occurs at candidate Stage 1 offset `0x808`; a naive startup_header decoding gave inconsistent size fields, so it is **not yet a verified loadable IFS**.

## Stage 2 container and imagefs

Candidate Stage 2 payload has `IFSPTTBL` at `0x7f8`, with two 44-byte records `STAGE2.1` and `STAGE2.2`. The observed Stage2.2 span is `[0x93cc90, 0x15fc090)`, length `0xcbf400`. For Stage2.1, `0x93cc87` and `0x174d718` are observed record values; a compressed/uncompressed length interpretation is **unconfirmed**. Nine bytes separate the candidate Stage2.1 length from the Stage2.2 start.

Within Stage2.2, an imagefs candidate starts at offset `0x890` (relative to Stage2.2), with parsed file records starting `0x908`. A previous pass recovered **344 candidate directory entries**. Two mappings were cross-checked against coherent ARM32 little-endian ELF headers:

| Path | imagefs-relative data offset | Stage2.2 ELF offset | Directory-reported length |
| --- | ---: | ---: | ---: |
| `bin/mostcoreapp` | `0x6000` | `0x6890` | 348,668 |
| `bin/imgdec` | `0x5c000` | `0x5c890` | 32,772 |

ELFs reportedly use `/usr/lib/ldqnx.so.2`. Their names suggest application components, **not** QNX kernel/startup. Importantly, the highest directory-reported end (`0x1bb5e2f`) extends beyond the Stage2.2 stored length. Do **not** assume all 344 entries can be extracted from this region as-is; check imagefs address mapping/packing.

## Remaining work and boot milestones

1. Revalidate imagefs records, file spans, and extract complete, in-bounds files; build a machine-readable manifest.
2. Determine Stage2.1 representation and whether `0x174d718` is an unpacked size.
3. Parse Stage1 QNX startup header against the correct QNX 6.5 layout; locate actual `startup`, `procnto`, and `.script` without guessing.
4. Establish the FPK1 memory map, CPU handoff, UART, flash layout, and boot prerequisites. Compare with `hw/arm/tegra30.c` and MHI2 machine.
5. Only then implement an isolated FPK1 machine profile; boot success means reaching original `procnto` and obtaining diagnostic output before attempting FPK applications or graphics.

Keep binary images out of Git. Preserve exact offsets, coordinate system (archive file vs unwrapped payload vs Stage2.2), hashes and validation commands in future tooling. 

## Imagefs bounds validation (follow-up)

The 344 parsed directory records describe a **logical image larger than the stored STAGE2.2 region**. For the 13,366,272-byte region (imagefs base at `0x890`), only **7 records** have an entire `base + data_offset .. + length` span inside the stored bytes; **337 extend past the end**. The seven in-bounds files are `data/gtf/MenuIcons/E09B_preview.png`, `bin/mostcoreapp`, `data/gtf/MenuIcons/E079.png`, `bin/imgdec`, `data/gtf/SourceHanSansKR-Regular.otf`, `data/gtf/SourceHanSansJP-Regular.otf`, and `data/gtf/ZYHei_GB18030_c.ttf`. The first out-of-bounds record is `data/gtf/atlas_full_LA.atlas` (logical offset `0xb31668`, length `1,708,769`). The maximum logical file end is `0x1bb5e2f`. This supports a larger logical address space but **does not yet identify compression, storage layout or missing flash parts**.

To reproduce against an independently extracted STAGE2.2 region: `python3 tools/fpk1/inspect_stage2_imagefs.py /path/to/stage2_2.bin --json /tmp/imagefs-extents.json`. The parser intentionally refuses unexpected marker offsets. Do not interpret out-of-bounds entries as extractable files.

## Stage2.1 imagefs size cross-check

The word `0x0174D718` occurs in **two independently located structures**:

- In the `STAGE2.1` partition record at payload offset `0x834`.
- In the embedded `#imagefs` sequence: tag starts at payload offset `0x8a0`, a one-byte marker `04` follows the tag, and the next little-endian word at `0x8a9` is exactly `0x0174D718`.

The match strengthens the interpretation that `0x0174D718` (24,434,456 bytes) is a **logical imagefs extent/size**, not an arbitrary unrelated value. It does **not**, by itself, establish a compression codec or successfully decompressed data. The Stage2.1 stored-length field is `0x0093CC87` (9,686,151 bytes).

For Stage2.2, the table gives start `0x93cc90` and length `0xcbf400`. The first `imagefs` text is at payload offset `0x93d520` (= region-relative `0x890`), rather than at the region's beginning. The first bytes at the Stage2.2 region start are `e5 08 33 3f e5 08 32 34 ...`, not a normal ELF header. Avoid treating the table boundary as a direct executable entry point.

Reproduce: `python3 tools/fpk1/probe_stage2_layout.py /path/to/FPK1-update.zip`. No proprietary content is tracked.

## Stage2.1 encoded content: preliminary observations

A reproducible probe on the original update archive confirms the Stage2.1 stored field `9,686,151` bytes, logical size `24,434,456` bytes (embedded in `#imagefs` as well), and ratio `2.5226:1`. The start of this region is **not entirely opaque**: early bytes include the readable paths `usr/lib/terminfo`, `/mnt`, `usblauncher`, and `etc/mcd.`.

A scan of the stored extent starting at `0x880` found **zero occurrences** of the common framed/container magic sequences for gzip, xz, bzip2, LZ4 frame, Zstandard frame and the conventional LZO container. This is not a codec identification: raw compressed streams, block-level schemes, or proprietary encoding are still possible. Do not apply arbitrary whole-region decompression or claim that a 24-MB decoded image was recovered.

Reproduce: `python3 tools/fpk1/probe_stage21_encoding.py /path/to/FPK1-update.zip --json result.json`. Next: establish the record/extent mapping between the readable imagefs metadata and encoded file-data blocks, and cross-check against Stage1 before attempting boot.

## Existing MHI2 Python tooling reusable for FPK1

Before inventing another IFS decoder, examine these files in the same repository:

- `tools/mhi2/extract_main_ifs.py`: handles MHI2's **LZOZ** block wrapper, reads a block-size word, a block-length table at offsets `0x8..0x7ff`, and 512-byte-aligned compressed blocks starting at `0x800`. It calls `liblzo2.lzo1z_decompress_safe`, concatenates blocks, then requires `imagefs` and extracts regular files. **LZOZ was not observed as an FPK1 Stage2.1 container signature**; reuse only after establishing a compatible wrapper/block encoding.
- `tools/mhi2/lzo_library.py`: portable ctypes loader for system `liblzo2`.
- `tools/mhi2/glforward/ifs_resource.py`: independently establishes QNX6 imagefs header fields: directory offset at +16 and data-start at +12; record size is a **16-bit** field at the record start; mode is at record +8; regular-file data offset/length are at +24/+28; file path starts +32. This should be the reference for rewriting/validating our tentative FPK1 parser, especially the record-size width.
- `tools/mhi2/prepare.py`: builds emulator boot media for the **MHI2 variant-70 partition layout**, uses a separately captured NOR/IRAM/eMMC bootstrap, and expects different firmware components. It is not directly suitable for FPK1 without a demonstrated boot-media mapping.
- `tools/mhi2/qnx6_image.py`, `qnx6_read.py`: QNX6 disk filesystem tools; distinguish them from the QNX boot `imagefs` format.

**Correction to earlier research assumptions:** the provisional FPK1 Stage2 directory parser should be validated against the 16-bit entry lengths and file-mode-dependent name offsets of the existing imagefs implementation, rather than declaring all 344 entries structurally verified. In particular, an uncompressed logical length is not evidence for any specific codec. Next: write fixture-based tests for an FPK1 read-only directory extractor based on the existing imagefs routines, then probe Stage2.1 for raw LZO blocks only with explicit validated sizes and boundaries.

## Corrected imagefs record parsing (cross-checked on original FPK1)

The same **16-bit record-length** and **file-type-aware name offset** from the existing MHI2 QNX parser are valid for FPK1 STAGE2.2. Direct binary validation now gives:

- Header at STAGE2.2 `+0x890`: `imagefs\\x04`; declared logical image size `0x01bb5e34`; data start `0x59dc`; directory starts at header-relative `0x5c` (region `+0x8ec`, not `+0x908`).
- **345 catalog entries total**, of which **344 are regular files** and **1 is a non-regular entry**. Directory ends at STAGE2.2 `+0x6268`.
- **7 of 344 regular files** fit completely into the stored region; the remaining **337** have at least part of their span outside. Maximum logical file end: `0x1bb5e2f`, five bytes short of the declared logical image size `0x1bb5e34`.

This corrects earlier wording that called all 344 entries the full catalog and incorrectly identified `+0x908` as the catalog beginning: that offset is the **first regular-file entry**, not the directory header's beginning. The independently matching maximum file end and declared logical image size show that the imagefs metadata is internally consistent, while its backing bytes still require reconstruction.

`tools/fpk1/inspect_stage2_imagefs.py` was revised to follow the MHI2 layout instead of treating the entry size as a 32-bit integer. The earlier file-boundary findings for the 344 regular files are preserved.

## Bounded LZO1Z probes (negative)

A first direct test used the installed `liblzo2.so.2` and the same `lzo1z_decompress_safe` entry point employed by MHI2. Candidate offsets in the unwrapped Stage2 payload were `0x8b1`, `0x8b5`, `0x8b9`, `0x900`, `0x1000`, `0x2000`. Each tested at most 65,536 input bytes with a 262,144-byte output buffer. **All six returned -6** (input overrun/incomplete stream), so there is no verified LZO1Z block recovery.

This **does not rule out LZO1Z**, since genuine start addresses, compressed lengths and output sizes have not been established. Do not label arbitrary slices as compressed blocks. The reproducible read-only probe is `tools/fpk1/probe_lzo1z.py`. Next investigate block boundaries and indexed extents before attempting decompression.

## Stage2 storage-boundary sampling

Read-only sampling of the original update (payload coordinates, HSP bytes stripped) gives a stronger baseline before speculating about a block codec. Entropy (Shannon bits/byte): Stage2.1 metadata `0x880..0x2000` **7.053**; middle `0x100000..0x110000` **7.524**; near-tail sample **7.340**; Stage2.2 first 4 KiB at `0x93cc90` **6.361**; middle `0xa00000..0xa10000` **7.460**; final 4 KiB **3.236**. The region is heterogeneous, so an arbitrary whole-region decompression is unwarranted. Low tail entropy is consistent with padding or structured data and is not proof of a codec.

The embedded Stage2.2 `imagefs\\x04` header reports logical size `0x01bb5e34`, while its stored region is `0x00cbf400`. Stage2.1's embedded `#imagefs\\x04` reports `0x0174d718` and its stored field is `0x0093cc87`. These are **two distinct logical-size declarations** and neither establishes the compressed-block table layout.

Reproduce with `python3 tools/fpk1/probe_stage2_regions.py /path/to/update.zip --json results.json`; the new script records sample offsets, entropy, common bytes and SHA-256 so hypotheses can be compared against future firmware builds.

**Next actionable target:** correlate directory data offsets with stored-byte extents; search for block-index metadata using verified record boundaries before attempting LZO1Z. Revisit Stage1 QNX startup for boot viability in parallel.

## Audit of the actual MHI2 firmware preparation pipeline

The repository's `tools/mhi2/build_firmware.py` is only a shim into `build_audi.py`; `build_audi.py` validates one of the supported MHI2 trains, invokes `prepare.py` with a captured NOR/IRAM/eMMC bootstrap, calls `extract_main_ifs.py` on `MMX2/mifs-stage2/70/default/mifs-stage2.img`, and then calls `prepare_ui.py`. This is an **MHI2 variant-70 workflow**, not a generic loader for arbitrary HSP-wrapped FPK1 update archives.

Two **distinct** compression schemes exist in the MHI2 scripts:

1. `extract_main_ifs.py`: main IFS starts `LZOZ`, block size at +4, compressed-length table at +8..+0x7ff, compressed blocks at +0x800 aligned to 512 bytes; uses LZO1Z.
2. `prepare_ui.py`: kernel partition has a fixed `0x800`-byte image header and a **zlib** stream at `+0x800`. The decoded image contains QNX startup/imagefs. This path must not be confused with the LZOZ main IFS.

Comparison of the original FPK1 `stage1_ifs.img`, `stage1_RECOVERY_ifs.img`, and `stage2_ifs.img` after stripping the *candidate* `0xc2` HSP prefix found **neither the `LZOZ` nor `ANDROID!` marker** in these three payloads. Probes for both zlib-wrapped and raw deflate streams at payload offsets `0`, `0x800`, `0x808`, `0x880`, `0x8a0`, `0x1000` did not yield a viable output >100 bytes in the first 128 KiB. These are bounded negative results, **not** proof that the images do not contain any deflate-compressed blocks.

Reproduce: `python3 tools/fpk1/compare_mhi2_wrappers.py /path/to/FPK1-update.zip --json report.json`. The next useful work is to identify FPK1's block layout from the contained imagefs and partition metadata rather than assume the MHI2 wrapper. Existing imagefs parsing logic **is directly reusable once logical bytes can be reconstructed**.

## Exact build_firmware.py media assembly path

Reviewed `tools/mhi2/build_audi.py` (the target of the `build_firmware.py` shim), `prepare.py`, and `prepare_ui.py` directly. This pipeline performs **boot-media construction/repacking**, rather than only pointing QEMU at an update archive.

1. `build_audi.py`: extracts the user archive with `7z`; checks `metainfo2.txt` release against one of three exact supported trains; validates three bootstrap inputs against SHA-256 from `bootstrap.json`; builds QEMU and bridge binaries.
2. `prepare.py`: clones 64 MiB base NOR and IRAM from capture; derives BCT pointer from IRAM; reads 13 entries in captured NOR partition table at `0x40040`. It verifies old stage2 CMAC, unpacks both `qb_primary.img` and `qb_recovery.img` into stage1/stage2 Quickboot pieces, adds NVIDIA AES-block padding, installs to named NOR partitions, and updates IRAM CMAC. It also installs the firmware's `mifs-stage1`, `eifs`, `mifs-stage2`, `efs-sys`, `efs-pers`. For kernel partitions it **replaces only the first eight bytes** with `ANDROID!` and verifies the header's CRC32; it does not decompress them here. It also clones formatted eMMC and injects the `app.img` filesystem.
3. `extract_main_ifs.py`: decompresses the main `mifs-stage2.img`'s `LZOZ` blocks using LZO1Z and parses the complete `imagefs`.
4. `prepare_ui.py`: modifies the kernel IFS held in prepared NOR (zlib stream from `+0x800`), adjusts `usr/sbin/startup.sh` for a diagnostic shell, recompresses and repairs header checksums; separately patches EGL/GLES resources in extracted main IFS, repacks its `LZOZ` blocks, writes resulting NOR and eMMC files and shader/metadata outputs.
5. Writes generated `run.sh` referencing built `qemu-system-arm`, bridges and prepared media.

**FPK1 implication:** the MHI2 construction path crucially relies on captured, device-specific NOR/IRAM/BCT and a formatted eMMC template. An update ZIP alone cannot be substituted for those inputs. We can reuse parsing and packing algorithms when layouts match, but cannot assume MHI2 bootstraps, partition IDs, Quickboot CMAC, or `MMX2/.../70/default/` update paths are interchangeable with FPK1. The immediate task is to map FPK1's update components to NOR/eMMC partitions and determine whether a valid FPK1 BootROM-to-AVP handoff can be reconstructed or supplied.

## FPK1 Quickboot comparison against the actual MHI2 assembler

Examined **both** `KI_FPK_AU536/gss-qb-primary/8/default/qb_primary.img` and `gss-qb-recovery/8/default/qb_recovery.img` from the supplied archive. Each file is 100,805 bytes; stripping the candidate 194-byte HSP wrapper leaves **100,611 bytes**. Those two payloads are **byte-for-byte identical**, although their signed HSP envelopes differ. Both payloads begin with `30 40 2D E9 00 30 A0 E3`, which looks like ARM instructions rather than the two u32 sizes expected by MHI2.

MHI2 `prepare.py` parses the first 8 bytes as `(stage2_size,stage1_size)` and requires `8 + stage2_size + stage1_size == len(raw)`. FPK1 payloads do **not** meet this invariant, so applying the MHI2 Quickboot split to FPK1 would be incorrect. It remains to be established how FPK1's Quickboot is loaded and whether an appropriate AVP/BCT handoff can be reconstructed. The common payload does **not** demonstrate identical runtime behavior of the primary/recovery paths.

Reproduce with `python3 tools/fpk1/inspect_quickboot.py /path/to/FPK1-update.zip --json qb-report.json`. No firmware bytes have been committed.

## Quickboot ARM code and unresolved linked addresses

A direct ARM-state probe of HSP-stripped `qb_primary.img` begins with `e92d4030` (`push {r4,r5,lr}`), `e3a03000` (`mov r3,#0`), `e24dd014` (`sub sp,sp,#20`) and `e59f4064` (`ldr r4,[pc,#0x64]`). This is a **function prologue**, not proof of an AVP/BootROM entry point. The `ldr` at file-relative `0x0c` reads the literal at `0x78` = `0x8401891c`; other PC literals at `0x7c`, `0x80`, `0x84` are `0x84068088`, `0x8401891c`, and `0x84068083`.

File-relative branches in the first 0x78 bytes: `0x1c -> 0x50`, `0x20 -> -0x54bf8`, `0x28 -> -0x56708`, `0x44 -> -0x54bf8`, `0x4c -> -0x56708`, and `0x68 -> 0x20`. The **negative targets are important**: this code may be a partial linked component with references outside the supplied blob, or require a different load context. Do not patch these branches or invent an entry address. Runtime address = unknown load base + file offset, and address calculations may depend on prior relocation.

The literal pool contains addresses in the Tegra DRAM range used by the MHI2 machine (`0x80000000` and above), but this is **not** evidence that the exact MHI2 layout or the `0x480e0000` AVP reset PC applies to FPK1. The primary and recovery payloads are identical in the researched update. Reproduce with `python3 tools/fpk1/probe_quickboot_arm.py /path/to/update.zip --json /tmp/qb-arm.json`.

**Next step**: determine if the Quickboot blob is a component intended to be linked/copied into an existing larger loader using FPK1 update metadata or if it has a nonzero load bias. To get first boot, investigate Stage1 startup and AVP handoff before trying to jump to the first instruction of this Quickboot blob.

## Quickboot linkage cross-file verification

The first 0x78 bytes of FPK1 Quickboot contain four ARM `BL` instructions with **negative file-relative targets** (in addition to internal control flow): `0x20 -> -0x54bf8`, `0x28 -> -0x56708`, `0x44 -> -0x54bf8`, `0x4c -> -0x56708`. These are approximately 340–354 KiB before the start of the payload, whereas the payload itself is only 100,611 bytes. This makes standalone execution beginning at file offset zero unsafe to assume: the code expects linked routines outside the provided payload, or a more complex load/relocation arrangement. No load base or valid execution entry has been established.

A cross-file scan of all `.img` and `.bin` members in the supplied archive found little-endian 32-bit literal values `0x8401891c`, `0x84068088` and `0x84068083` **only within the two Quickboot files** (which have identical payloads), not in the other update images. That limits simple literal-matching as a method of identifying the linked companion binary; it does not rule out other representations, compiled code, or files absent from the update.

Reproduce using `python3 tools/fpk1/audit_quickboot_linkage.py /path/to/update.zip --json results.json`. **Do not** set the Tegra AVP PC to this blob's first instruction until its actual loading context is understood. Next priority: identify the installed Quickboot memory position and dependency in FPK1 firmware/update metadata or on-device dumps; in parallel resolve the Stage1 ARM startup header/boot script.

## Stage1 candidate validated against QNX 6.5 startup_header definition

Used the field order and exact 256-byte `struct startup_header` described in QNX 6.5 *Building Embedded Systems*, rather than offset guesses (https://qnx.com/developers/docs/6.4.0/neutrino/building/load_process.html and https://www.qnx.com/developers/docs/6.5.0SP1.update/index.html). At payload offset `0x808`: signature `0x00ff7eeb`, version `0x2001`, flags1 `1`, flags2 `8`, header_size `0x100`, machine `0x28` (ARM), startup_vaddr `0x80a06b98`, image_paddr `0x80a00808`. These are plausible *candidate* metadata.

**However**, the same layout yields `startup_size=0x400001a1` and `stored_size=0x04004007`; both exceed the ~2-MB stored Stage1 payload, and startup_size > stored_size. This contradicts the QNX startup-header invariants. Do not assume `0x80a06b98` is an operational entry address, and do not feed this candidate directly into QEMU. Potential explanations (not established): modified header, false-positive embedded signature, or additional transformation/relocation.

Reproduce using `python3 tools/fpk1/validate_stage1_startup_header.py /path/to/FPK1-update.zip --json stage1-header.json`. Immediate next check: compare the 256-byte header against QNX `dumpifs` on native equipment or BSP code, and inspect image start/base semantics before any boot attempt.

## Tegra30 QEMU boot handoff: concrete source audit

Reviewed `hw/arm/mhi2_harman.c`, `hw/arm/tegra30.c`, and `include/hw/arm/tegra30.h` from main. MHI2 uses a **captured post-BootROM handoff**, not full NVIDIA BootROM emulation:

- `mhi2_reset` resets AVP and A9/LP CPUs, then sets **AVP** PC to `0x480e0000`. The Cortex-A9 CPUs are held in reset until boot code releases them.
- In the MHI2 machine, the firmware file must be **exactly 64 MiB** and is provided as a NOR image. A `rom_add_blob_fixed` shadow copies the NOR content at `0x83f28000`; the actual flash is also exposed via a Tegra SNOR model/window at `0x48000000`. These are board-specific choices.
- IRAM is mapped at `0x40000000`, size `0x40000` (256 KiB). `-machine iram=<image>` seeds IRAM with a captured Boot Information Table and BootROM results; without it the machine explicitly refuses boot.
- The CPU reset-vector registers around `0x6000f100` are modelled in the SoC, allowing AVP firmware to release the main CPU after writing the entry address.

These facts establish a **possible design pattern** for FPK1: keep common Tegra30 SoC, define a distinct FPK1 board machine with explicit boot handoff inputs and optional read-only diagnostic tracing. They do **not** establish that FPK1's real NOR is 64 MiB, that its Quickboot is mapped at `0x83f28000`, or that its AVP boot PC equals `0x480e0000`.

### Diagnostic prerequisites before boot attempt

1. Identify FPK1-specific flash map and BCT/IRAM handoff (or explicit evidence for an alternative stage1-direct boot).
2. Determine FPK1 startup's actual physical load address and valid entry point; current Stage1 candidate has contradictory `startup_size` / `stored_size` fields.
3. Introduce a separately named `fpk1` machine only with validated, selectable boot addresses/inputs. Log failures on missing input rather than silently using the MHI2 captured NOR/IRAM.
4. For diagnostics use CPU tracing and unimplemented-MMIO logs at the first validated handoff. A working `procnto` is the first boot milestone, not successful ARM execution alone.

No execution of FPK1 firmware in QEMU has yet been demonstrated.

## Live FPK1 Stage1 AVP trace and QNX header validation (Mac smoke test)

User-built QEMU macOS `fpk1` diagnostic machine passed a meaningful instruction test: AVP CPU #5 executed a generated `mov r0,#42; b .` payload, resulting in `R0=0x2a` and `PC=0x80010004`. Thus AVP ARM execution is demonstrated, independently of OEM firmware boot.

With **HSP-stripped Stage1** (length `0x1f7000`) loaded verbatim at hypothetical `0x80a00000`, the first two words at file offset `0x800` are `E28FC00C; E59CF000`: a valid ARM entry stub. The stub fetched `0x80a06b98` from file offset `0x814` and did branch there, as corroborated by the actual QEMU `in_asm,exec` trace. It subsequently traversed seemingly invalid code and zero-filled RAM (`0x81a073a8`, then further to `0x82ce0800`). **This does not establish a usable QNX startup image.** The observed execution is a bad boot / wrong layout, not a successful OS handoff.

The QNX 6.5 source-defined `startup_header` at payload `0x808` has signature `0x00ff7eeb`, version `0x2001`, header size `0x100`, machine `0x28`, and startup_vaddr `0x80a06b98`. However, decoding its remaining 32-bit fields according to `sys/startup.h` yields `startup_size=0x400001a1`, `stored_size=0x04004007`; neither fits the `0x1f7000` bytes available. Under standard QNX IPL semantics, the startup executable must be copied **uncompressed**, even when the rest of the IFS is compressed; this makes blindly searching for zlib at the entry address unproductive. Reference: https://qnx.com/developers/docs/6.4.0/neutrino/building/load_process.html (QNX startup_header and IPL semantics).

A user-run bounded probe at payload offsets `0x0`, `0x800`, `0x808`, `0x900`, `0x1000`, `0x2000`, `0x6b98` found no meaningful zlib/raw-deflate stream; a raw-deflate false positive at `0x900` returned only 5 bytes. Pattern scanning ARM prologues also found many unaligned hits, so they are not reliable entry candidates.

Added `tools/fpk1/compare_stage1_headers.py` to compare ordinary/recovery Stage1 QNX startup-header **invariants** and report raw fields, without claiming a compression method or executable load point. Reproduction (from the repository root):
```sh
python3 tools/fpk1/compare_stage1_headers.py /path/to/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip --json /tmp/fpk1-stage1-headers.json
```

## Stage1 primary/recovery comparison (local macOS extraction)

The `compare_stage1_headers.py` tool was executed locally against the original Q7 2018 update. Primary: HSP raw 2,060,482 B, candidate unwrapped 2,060,288 B; **one** QNX startup magic at payload `0x808`. Recovery: HSP raw 8,743,106 B, candidate unwrapped 8,742,912 B; **no** occurrences of that QNX startup magic. This is only a signature-search observation: **do not conclude recovery cannot contain QNX**, as alternate offsets/wrapping and transforms have not been identified.

The primary header has `startup_size=0x400001a1`, `stored_size=0x04004007`, exceeding the complete stored payload and violating `startup_size <= stored_size`; the regular `sys/startup.h` representation therefore fails invariants. Crucially, the whole `startup_header` occupies 256 bytes **from signature at 0x808 through 0x907**. Bytes near `0x83c`, `0x900` and ARM-prologue-like subsequences within that header are **not** independent evidence of executable startup code. The `startup_vaddr=0x80a06b98` is genuinely embedded as an entry address in the header and is followed by anomalous bytes at file-relative `0x6b98`; the AVP trace demonstrates a bad, unsatisfied handoff when the raw payload is directly loaded.

Keep two independent hypotheses: (a) QNX-header lookalike inside a transformed FPK1 blob, or (b) a real QNX header with vendor-specific packing/relocation. Neither is established by a magic match alone. Do not patch header bytes or claim a working IFS until an original loader/format specification confirms its representation. Primary next step: inspect image/container layout and recovery's first 0x1000 bytes, compare byte statistics and aligned prefixes, and test whether candidate lengths/addresses can be independently justified. Source definition: https://qnx.com/developers/docs/6.4.0/neutrino/building/load_process.html

## Primary vs recovery Stage1 container: macOS measurements

A user's independent scan of the original update yields two candidate HSP-stripped payloads:
- Primary: size `0x1f7000`, SHA256 `08985273359746532617c5a7446d0ece46fa339d33e5ab335cf94e0a26ef21d2`; LE u32 at payload +0 = `0x001f656c` (difference `0xa94` from payload length), QNX startup magic at +`0x808`, `imagefs` literal at +`0xe530`, no `LZOZ` signature.
- Recovery: size `0x856800`, SHA256 `56e8844b8a1e5e3439ce1f70f57265c15277636cbf15a3301bb0c7d2f161369c`; LE u32 at +0 = `0x00855a2f` (difference `0xdd1`), neither QNX magic nor `imagefs` nor `LZOZ` seen.
- Both headers show matching bytes after the initial size field (notably u32 at +4 = `0x00a00800`, and ASCII `root=/...` in the first 64 bytes). This strongly suggests a shared **container header** despite radically different contents. The first u32 may represent a stored length or other size; there is *not yet* evidence that it defines the complete encoded-data extent.
- Entropy of Primary 4-KiB windows at payload +`0x800`, +`0x1000`, +`0x2000` = 6.582, 6.699, 6.720 bits/byte, while Recovery reports 7.913, 7.920, 7.913 bits/byte. Recovery may be compressed or encrypted; this does **not** distinguish those hypotheses.

New `tools/fpk1/compare_stage1_containers.py` compares first 0x800 bytes excluding the length field, finds the first other difference, measures short-region entropy, and reports raw length-field residuals. Running it on the same archive will determine exactly how much of the apparent header is shared. Do not interpret the QNX magic in the primary as a sufficient demonstration of a valid unpacked bootable IFS.

## Stage1 control-field differences (user-verified byte diff)

Primary and recovery unwrapped headers differ at exactly 17 byte positions in `[0x04,0x800)`: `0x258` is a 32-bit little-endian field with values **2** vs **1**; `0x25c..0x25f` holds `0x9ca5b5ee` vs `0x8953d25f`; `0x7f4..0x7ff` is a distinct **12-byte** field per image. All earlier header fields match. Payload begins at `0x800` in both; primary starts with QNX ARM stub, recovery starts with high-entropy data.

Both files end in the identical eight-byte sequence `68 65 50 0e 01 00 00 00`, preceded by zero padding. This is a potential footer marker, **not yet a decoded record**. Payload byte-counts exceed the little-endian field at +0 by `0xa94` (primary) and `0xdd1` (recovery); neither proves the field's purpose or an exact payload boundary.

The proximity of mode-like u32 `0x258`, another u32 `0x25c`, and 12 bytes just before the payload suggests a common structured update container. **Do not label those bytes encryption nonce, HMAC, IV or CRC until validated.** Read-only `tools/fpk1/probe_stage1_integrity.py` tests several standard CRC32 / Adler32 ranges against the u32 field and reports footer/zero-padding characteristics for both images.

## Stage1 declared-size arithmetic invariant

User-run `probe_stage1_integrity.py` found no CRC32 or Adler32 equality with `u32@0x25c` in six tested regions per variant. **This rejects only those exact hypotheses**, not other checksum ranges/algorithms.

An exact invariant occurs in *both* candidate payloads:
`len(payload) - u32le(payload,0) = 0x800 + trailing_zero_run_before_last_8_bytes`.
Primary: `0xa94=0x800+660`; recovery: `0xdd1=0x800+1489`. Both share an 8-byte footer `6865500e01000000` preceded by those zeros. The relation is strong evidence for a fixed 0x800-byte container header and a recorded length associated with content and trailing layout. **However, the declared end `0x800+size` is actually 8 bytes *into* the zero run (not the footer), so neither an exact footer-inclusion rule nor padding alignment has been established.** Do not trim, repackage, or boot based on an invented boundary.

`tools/fpk1/probe_stage1_integrity.py` now reports this size identity and the distances from declared end to both the beginning of the zero run and the footer. Next: inspect last nonzero bytes before the padding, probe exact header/footer semantics in the installer code and further images.

## Stage1 payload exact declared-size boundary — verified directly against original ZIP

Both HSP-stripped Stage1 variants satisfy an identical arithmetic relation, now checked against the actual bytes, not merely inferred from entropy:

- Primary: `payload_length=0x1f7000`, `u32le@0=0x1f656c`, `declared_end=0x800+0x1f656c=0x1f6d6c`, `last_nonzero_end=0x1f6d64`, **8 zero bytes** at `[0x1f6d64,0x1f6d6c)`, further 660 padding zeros in total before the last 8-byte footer.
- Recovery: `payload_length=0x856800`, `u32le@0=0x855a2f`, `declared_end=0x800+0x855a2f=0x85622f`, `last_nonzero_end=0x856227`, **8 zero bytes** at `[0x856227,0x85622f)`, further 1489 padding zeros in total before the same footer.
- The identical end-of-container footer is `68 65 50 0e 01 00 00 00` at `payload_length-8`; it is **outside** the declared region in both variants.
- The Primary bytes immediately before the 8-byte zero run include an intelligible startup script line ending `/bin/login" vt100 on\n`, a NUL, and eight nonzero bytes `b1 97 95 25 f7 3f a1 53`. Recovery ends instead with `... 05 4e 38 fb ee` (high-entropy data). The last 8 nonzero bytes are **unidentified**; do not label them a signature or checksum without proof.

This reinforces that `u32@0` is a container-relative length covering the region beginning at `0x800`, including exactly 8 trailing zeros for both observed images; it does **not** include final flash padding or the 8-byte footer. It does not yet tell us the meaning of the nonzero 8-byte tail or whether either image is otherwise compressed/encrypted.

`tools/fpk1/probe_stage1_integrity.py` now reports exact significant-data end and declared-region final eight bytes. The next reverse-engineering priority is correlating `u32@0` and the fixed footer with the real installer or HSP image writer, and discovering the Recovery-specific encoding indicated by the mode field `u32@0x258` (1 vs 2).

## Cross-image control field evidence (original Q7 ZIP)

Direct inspection across the update's HSP-wrapped `.img`/`.bin` entries establishes two important corrections:

- The eight-byte trailer `68 65 50 0e 01 00 00 00` occurs **in the HSP-stripped representation of many different components**, including `qb_primary.img`, `qb_recovery.img`, `stage1_ifs.img`, `stage1_RECOVERY_ifs.img`, `stage2_ifs.img`, `stage2_nand.img`, `stage3.img`, `app.img` and the other HSP-wrapped binaries checked. It is **not specific to Stage1**. Its origin may be the signed update packaging itself rather than an IFS container terminator; no encoding definition is established.
- `stage2_ifs.img` shares the candidate Stage1 envelope shape: LE word at payload +4 = `0x00a00800`, u32 at +`0x258` = **1**, and u32 at +`0x25c` = `0x6c920e6e`. Primary Stage1 has mode **2**, Recovery Stage1 mode **1**. Thus mode 1 is **not exclusive to recovery**. Stage2's 12 bytes at `0x7f4` terminate with `IFSPTTBL`, unlike Stage1. These fields are likely specific to an update-image envelope; do not classify 1/2 as encryption/cipher modes without an installer-side decode.
- `qb_primary.img` begins with ARM instructions immediately after HSP; `app.img`, `stage3.img`, and others show diverse bytes at identical offsets. Applying `u32@0` or `mode@0x258` as universal HSP fields would be wrong.

Added `tools/fpk1/inventory_hsp_payloads.py` to audit the format differences and the cross-image trailer without writing proprietary binaries. Follow-up: group only images that have verified common envelope features, inspect their respective metadata and staging algorithms, and avoid blind encryption claims.

## Full HSP inventory: candidate IFS family vs other payloads

User-run `inventory_hsp_payloads.py` on the actual FPK1 ZIP found **three** payloads sharing `u32le@0x04=0x00a00800`: Stage1 Primary (`mode@0x258=2`, size `0x1f656c`), Stage1 Recovery (`mode=1`, size `0x855a2f`), and Stage2 IFS (`mode=1`, size `0x15fc138`). For all three, the declared extent starts at `0x800`, ends before a zero-filled tail, and is followed by the shared eight-byte external footer. The common footer is an HSP packaging feature and alone is **not** sufficient to identify a filesystem.

Other HSP-wrapped components have different layouts: Quickboot is ARM code at payload +0; app and stage3 have apparently high-entropy bytes at +0; `stage2_nand.img` has `u32@0=0xe8` and no common `0x00a00800` word. An earlier `length_relation=true` for `stage2_nand.img` was a **false positive from a too-weak inequality**, not evidence of this container family. The inventory tool now explicitly reports `ifs_container_candidate`, requiring the shared header word, bounded declared length, zero-fill from declared end to footer, and common footer.

**Do not infer that mode 1 means recovery or encryption:** Stage2 uses mode 1 while normal Stage1 uses mode 2. Next investigation should prioritize how the update installer processes these three IFS members and how their inner bytes correspond to logical QNX structures.

## Signed update metadata separates KSS compression from Stage1/Stage2 packaging

Directly inspected the original Q7 2018 ZIP `*_SignInfo.xml` descriptors and their matching HSP-wrapped members. `START-BYTE-FLASHDATA=186` for the checked images, whereas the research scripts' current candidate payload begins at **0xc2 = 194**. The eight-byte difference must be explained before claiming exact externally signed data boundaries; the 0xc2 assumption is a *separate* inner-payload hypothesis.

Update metadata:
- `gss-stage1/.../stage1_ifs.img`, block 50: `COMPRESSED-SIZE=2060288`, `UNCOMPRESSED-SIZE=2060288`.
- `gss-stage1-recovery/.../stage1_RECOVERY_ifs.img`, block 51: both `8742912`.
- `gss-stage2/.../stage2_ifs.img`, block 52: both `23056384`.
- `kss-application/.../KSSApplication.bin`, block 16: `599730` stored vs `1048564` unpacked.
- `kss-flashdriver/.../KSSFlashDriver.bin`, block 1: `866` stored vs `1144` unpacked.

Thus update **transport-level compression** is declared for KSS app and flashdriver but *not* for the three IFS members. This **does not** rule out compression/encryption internal to the Stage1/Stage2 containers. KSS flashdriver data at candidate payload +0 starts `01 50 b7 0c 04 bf...` and appears Thumb-like; KSS application data starts `01 00 00 01 08 f1...`. Neither is an ELF and neither contains the literal `imagefs` or `IFSPTTBL`; there is no evidence yet that these KSS files parse the IFS container or decode its mode field. They may be packed before execution.

Added `tools/fpk1/inventory_signinfo.py` to independently verify all original SignInfo stored/unpacked sizes and external data-start offsets. The previous speculative proposal to look for raw IFS-parser literals in KSS must be revisited: first establish transport decompression of KSS or identify the relevant firmware updater in Stage2.

### Confirmed signed-data interval: correction to candidate 0xc2 slice

For the original Stage1 Primary, `raw_length=2060482`, `START-BYTE-FLASHDATA=186`, and `COMPRESSED-SIZE=2060288`: `186 + 2060288 = 2060474 = raw_length - 8`. The same arithmetic holds for Stage1 Recovery and Stage2 IFS using the published per-member sizes. Consequently, the **SignInfo-declared flash data is `raw[0xba:len(raw)-8]`**, while prior reverse-engineering scripts treated `raw[0xc2:]` as the payload. These ranges are **offset by eight bytes** and have equal sizes. `raw[0xba:0xc2]` is a per-format eight-byte marker: Stage1 Primary and Recovery have `41 ff 44 ff 4f ff 44 ff`, while Stage2 IFS has `43 49 46 53 00 00 00 00` (ASCII `CIFS` and four zero bytes). These are not interchangeable; their meaning has not been established. The common `68 65 50 0e 01 00 00 00` tail lies OUTSIDE SignInfo FLASHDATA; it is an update wrapper trailer, not proof of an IFS footer.

**Migration caution:** keep historical research offsets explicitly labelled `candidate inner payload offsets (raw+0xc2)`. To match SignInfo, prepend the eight-byte leading marker and omit the eight-byte trailer. This changes logical lengths, padding interpretations, and the previous assertion that `u32@0` ends eight bytes into the zero run: previous analyses apply to an eight-byte-shifted representation and MUST NOT be promoted to validated format specifications. E.g., file offset `raw+0x8ca` is candidate-inner `0x808` but SignInfo FLASHDATA-relative `0x810`. The ARM stub remains at raw offset `0x8c2`, or candidate-inner `0x800`, but signed-data-relative `0x808`.

The user-provided AVP trace remains a legitimate experiment on the **candidate inner image**, not proof that the update installer uses that inner representation without transformation. Prefer computing both offsets in future tools and never stripping the HSP header with an unexplained constant alone.

## SignInfo full inventory: actual outer zlib candidates

User-run `inventory_signinfo.py` confirmed each HSP member has **exactly 8 bytes after** its declared `START-BYTE-FLASHDATA=186` plus `COMPRESSED-SIZE`; those bytes are universally `6865500e01000000`. This is strong evidence for an external update-wrapper trailer, not an inner IFS footer.

The members with declared transport compression are:
- `app.img` (block 55): 1,577,543 stored → **209,715,200** uncompressed bytes; signed FLASHDATA begins `78 9c ec dd...` (zlib stream signature).
- `stage3.img` (block 54): 7,335,155 stored → **209,715,200** bytes; begins `78 9c ec dd...`.
- `KSSApplication.bin` (block 16): 599,730 stored → **1,048,564** bytes; begins `00 04 f0 1f e5...`, **not** zlib at byte 0.
- `KSSFlashDriver.bin` (block 1): 866 stored → **1,144** bytes; begins `00 00 00 00 04 99...`, **not** zlib at byte 0.

All three IFS entries (stage1 normal, stage1 recovery, stage2) have matching compressed/uncompressed sizes *in SignInfo*. That is no claim about internal IFS packing. A decisive next step is to decompress `app.img` and `stage3.img` directly from the **SignInfo-specified** byte ranges, checking stream EOF and exact output size, then identify the resulting image partition signatures. KSS will require its own compression/container interpretation.

Added `tools/fpk1/probe_signinfo_zlib.py` for a read-only check of all members with declared compression (256 MiB per-image output cap). It reports only size, zlib EOF, unused bytes and prefix; it does not write proprietary decompressed data. No success result is asserted until it is run on the original archive.

## Confirmed Stage3/app zlib transport, exact output

User ran `probe_signinfo_zlib.py` against Q7 2018 archive:
- `app.img` stored 1,577,543 → 209,715,200 bytes; `status=ok`, `eof=true`, `unused_bytes=0`.
- `stage3.img` stored 7,335,155 → 209,715,200 bytes; `status=ok`, `eof=true`, `unused_bytes=0`.
- Both unpacked byte streams begin with the same first 16 bytes `eb1090000000000010000000f83f0600`. This establishes identical prefixes, **not** identical images or a known filesystem/partition layout.
- `KSSApplication.bin` and `KSSFlashDriver.bin` rejected raw zlib-at-offset-zero (errors `incorrect header check` and `unknown compression method`). They may use other wrappers, compression methods, or mixed raw/compressed regions.

Added `tools/fpk1/inspect_decompressed_partitions.py`: read-only exact SignInfo zlib unpacking for these two members, 4-KiB nonzero range inventory, SHA256, and magic offset candidates. No extracted image files are written. Magic matches can occur by chance inside binary payloads and are **not sufficient** to declare a filesystem; offsets 0x438/0x1fe/0x200 are independently reported to test conventional ext/MBR/GPT placements. Follow-up: compare hashes, nonzero extents and verified partition format before choosing QEMU eMMC geometry.

## App/stage3 expanded 200 MiB disk reconnaissance (user measurements)

The two independently verified zlib-expanded images have different SHA256 values: app `274e12cf205c89b77af2c15562645a7917b850b41e4dec632e5600d4c61c8b78` and stage3 `b6abab7b536e69032491a6ae5e8245ea2395398a58a08ece48e3a4e0704976f3`. Their first 64 bytes are identical and both have `55 aa` at byte offset `0x1fe`, an MBR/boot-sector signature candidate. At offset `0x200` neither has `EFI PART`, so conventional GPT is unsupported. An isolated `55aa` **does not establish** a valid MBR partition table, filesystem, or FAT format.

Primary nonzero extents in app are sparse: `0x0..0x1000`, `0x2000..0x4000`, `0x9000..0xb000`, `0xd2000..0xd3000`, `0xd8000..0xda000`, `0x1a2000..0x348000`, and `0xc7ff000..0xc800000` (4KiB resolution). Stage3 has 79 reported extents and more used regions. Both have nonzero bytes close to the end of their respective 200-MiB output, indicating that trimming at the early dense areas would be unsafe.

Added `tools/fpk1/inspect_disk_partitions.py` to parse the four standard MBR records at `0x1be`, validate status, type, sector count, start/end LBA against the actual 409,600 sectors, and inspect the first sector at each plausible partition start. No claim of FAT, ext, or other filesystem should be made until partition descriptors and superblocks are validated. The tool does not write binary images.

## Expanded app/stage3 sector comparison: MBR and FAT rejected

User-run `compare_expanded_disk_images.py` reports that the initial 512-byte sector SHA256 is identical in the two 200 MiB images (`4dcaa9d3c4cb5d7be6f765bf7760c26550d32b3b51925da6b18b4edc27b327c2`), first 4096 bytes identical, and the first differing **sector** is LBA 16 (byte offset `0x2000`). Of 409,600 sectors, 366,872 match and 42,728 differ. Matches include abundant zero-filled sectors and must not be mistaken for file-level similarity.

The potential MBR records at `0x1be` have invalid active bytes `0x56`, `0xe8`, and huge out-of-bounds partition extents. FAT boot parameter interpretation is also impossible (bytes/sector 63488; sectors/cluster 63; zero FAT copies). The usual GPT marker is absent at LBA1. Thus **MBR partitioning and conventional FAT at offset 0 are rejected** despite boot-sector-like `eb1090` prefix and `55aa` at offset `0x1fe`. These two byte patterns are not sufficient to specify the boot architecture. An x86 real-mode bootstrap is a plausible interpretation, still unconfirmed by control-flow disassembly. Do not attach these images as verified MBR disks in QEMU.

New `tools/fpk1/inspect_early_disk_sectors.py` reports the exact first differing *byte*, sha256/nonzero count and hex samples of selected early sectors, especially LBA16, as well as sector-level differences in the first 256 sectors. This will guide identification of a custom volume/boot layout before implementing a disk controller.

## Expanded disks: first byte difference at 0x2004 and structured early sectors

User-run `inspect_early_disk_sectors.py` found **first differing byte = 8196 (0x2004)**, within LBA16 (base `0x2000`). The first four bytes of the two sectors match (`22 11 19 68`); bytes +4..+7 diverge: app `62 5a c9 de` vs stage3 `49 49 53 54` (ASCII `IIST`). Both then contain `01 00 00 00`. This is a *structured metadata candidate*, not yet a known filesystem magic. A targeted public lookup for `IIST` and the fixed four-byte prefix did not identify a reliable documented format.

At LBA24 (`0x3000`), the first 64 bytes are little-endian sequential integers 1..16, suggesting an index / map rather than executable code. LBA25 is all `ff` in both images. App LBA26 has a mix of `ff` then zeros while stage3 LBA26 is all `ff`; LBA84 and LBA85 contain records whose first 16/32 bytes differ by image but share structure. The early differences continue across LBA84 onward in stage3; many sectors are entirely zero. These are structure hints only: neither filenames, partition starts, nor filesystem type has been identified.

**Priority shift:** before implementing a QEMU disk layout, determine the invariant signature at LBA16, inspect little-endian fields and cross-sector pointer patterns for LBA16/24/84 and their counterparts in app/stage3. Establish which absolute/relative sector references are used. Avoid treating these as normal MBR/GPT partitions or assuming `IIST` is a format name.

## Identified filesystem: QNX6 Power-Safe (source-verified)

The byte sequence at offset `0x2000` in both zlib-expanded 200 MiB `app.img` and `stage3.img` begins `22 11 19 68`, which decodes to little-endian `QNX6_SUPER_MAGIC=0x68191122`. Linux's `Documentation/filesystems/qnx6.rst` specifies both the magic and the primary superblock offset `0x2000` (8 KiB bootblock). This **identifies QNX6 filesystem structure**, rather than an unknown x86 disk layout. Verified references: https://android.googlesource.com/kernel/common/+/refs/heads/android-mainline/Documentation/filesystems/qnx6.rst and https://github.com/torvalds/linux/blob/master/fs/qnx6/super_mmi.c . The four bytes at superblock+4 are checksums (app `62 5a c9 de`, stage3 `49 49 53 54`), **not** ASCII `IIST` describing an image format.

Linux QNX6 reader uses CRC32 big-endian polynomial `0x04c11db7` with initial CRC 0 over superblock bytes 8..511, comparing to little-endian stored u32 at +4. Tool `tools/fpk1/verify_qnx6_superblocks.py` performs this precise read-only verification for the original ZIP images and lists candidate superblock offsets; it has not yet been executed on the user's local archive. Follow-up: validate superblock checksum(s), geometry, inode and directory roots, and only then extract a file tree via a trusted read-only QNX6 parser or driver. QEMU emulated storage should expose the raw uncompressed QNX6 volume without inventing MBR partitions.

## Valid primary and backup QNX6 superblocks (user-verified)

The user ran `verify_qnx6_superblocks.py` on both zlib-expanded 200 MiB filesystems. In **both** images, the QNX6 signature at byte `0x2000` has a valid CRC32-BE over the 504 subsequent bytes, and a **byte-identical valid backup** superblock is at byte `0xc7ff000`. Both serials = 1. App CRC field `0xdec95a62`; stage3 CRC `0x54534949` (the ASCII-looking `IIST` is purely an accidental checksum representation). Additional magic matches at `0x207` in both images and `0x5be0bf` in stage3 are **false positives**: CRC mismatches with code bytes.

The Linux QNX6 on-disk structure is now a sufficiently grounded parser target: `include/linux/qnx6_fs.h` defines superblock geometry fields (blocksize, inodes, blocks) followed by four 80-byte root nodes: Inode, Bitmap, Longfile, Unknown. Reference https://codebrowser.dev/linux/linux/include/linux/qnx6_fs.h.html . The documentation explains that filesystem block zero begins at byte `0x3000` for a normal QNX6 image with an `0x2000` boot block and `0x1000` reserved superblock area. Reference https://kernel.org/doc/html/v6.18/filesystems/qnx6.html .

Added `tools/fpk1/inspect_qnx6_geometry.py` to read these fields, verify the **computed** secondary superblock address, and dump root pointers and levels for both volumes without extracting any proprietary files. The tool has not yet been run against the original ZIP. Do not interpret inode pointers until the derived block size and bounds have been checked.

## Corrected QNX6 geometry parsing — standard layout, not Audi MMI variant

User ran the initial `inspect_qnx6_geometry.py` and got impossible `blocksize=3013492499` (app) and `3959065292` (stage3), with impossible huge root-file sizes and backup offsets out of bounds. **These values were caused by a parser bug**, not invalid filesystems. The original tool read `blocksize` at `0x2c` and roots at `0x44`, both four bytes too early for **standard** `struct qnx6_super_block` in Linux `include/linux/qnx6_fs.h`. Correct offsets: `blocksize@0x30`, followed by five u32 fields through `allocgroup@0x44`, root Inode at `0x48` with 80-byte stride. See https://code.googlesource.com/linux/torvalds/linux/+/78273df7f646f8daf2604ec714bea0897cd03aae/include/linux/qnx6_fs.h .

From the **already posted app superblock hex**, the corrected standard QNX6 geometry resolves `blocksize=1024`, `num_inodes=6400`, `free_inodes=6392`, `num_blocks=204784`, `free_blocks=201436`. Calculated secondary offset `0x3000 + 204784 * 1024 = 0xc7ff000` **exactly** matches the verified secondary CRC-valid superblock in both app/stage3. This independently confirms standard QNX6 geometry over an Audi MMI-variant interpretation. Root-node values output by the old tool are invalid and should be discarded. The corrected tool will report roots from offset `0x48` when rerun.

Commit fixes `tools/fpk1/inspect_qnx6_geometry.py` to correct both offsets and bound the block size to known valid values before calculating the backup address.

## QNX6 filesystem trees recovered (user-run recursive inventory)

The user ran `inventory_qnx6_tree.py`, confirming working inode pointer traversal and root directories. `app.img` has eight reachable entries: `/.boot`, `/dp/dp_monitor_types.xml` (303 bytes), `/dp/dp_monitor.cfg` (323602), `/img_ver.txt` (4), `/models/AU736_CarWarnings.kzb` (1388907). `stage3.img` has 289 reachable entries, including `/bin/stage3.sh` (359), `/bin/startup-common.sh` (953), `/bin/app/swdlclient`, `/bin/app/swdlmgr`, `/bin/driver/devf-tegra2-mmx`, `/bin/driver/devb-ram`, `/etc/mcd.mnt` (431), `/etc/scripts/extnet.sh`, `/etc/usblauncher/rules.lua`, and standard QNX userland commands/libraries. This establishes that `stage3.img` contains a usable QNX userland tree, **not** that the earlier Stage1 AVP boot now succeeds.

Added read-only targeted text inspector `tools/fpk1/inspect_qnx6_startup_text.py` to retrieve only a short allowlist of startup scripts, mount configuration and version text (no passwords/shadow/keys or binary export), directly from SignInfo-validated ZIP. Its results are not yet available. Next: inspect actual launch sequence and mount points from script contents before constructing an emulated storage graph; do not infer boot order from filenames alone.

## Actual Stage3 startup and service dependencies (extracted from QNX6)

A user ran `inspect_qnx6_startup_text.py` and supplied actual text from the signed update's verified QNX6 Stage3 filesystem. This is now *observed script content*, not a guessed boot order.

`/bin/stage3.sh` (359 B) creates `/mnt/temp_fpk/screenshots` when missing, executes `ksh /stage3/bin/startup-common.sh`, runs `devg-nvtmon`, launches `diagnosis &` and `/bin/on -p 8 /stage3/bin/app/fds &`, runs core-dump initialization and `qnx_get_time`, then starts `/stage3/bin/grengme &` with `LD_LIBRARY_PATH=/lib:/lib/img_codecs:/lib/factories` and `LIBIMG_CFGFILE=/config/img.conf`.

`/bin/startup-common.sh` (953 B) sets LIBPATH and PATH, invokes `usb_init`, waits for `/dev/nvgpio/vcm_usb_on1` and writes zero, starts `io-pkt-v4-hc -vvvv -ptcpip` and `inetd /etc/inetd.conf`, creates a QNX RAM block device `devb-ram cam quiet ram capacity=2048 blk cache=512k,automount=hd0t77:/ramdisk`, then `pps -m /ramdisk/pps` and two `usblauncher` processes with `/etc/usblauncher/rules.lua`, `rules_most.lua` and `/etc/mcd.mnt`. It starts `autolauncher`, background `devn-usbinic` after `/dev/io-usb/io-usb-most`, invokes **`devf-tegra2-mmx -x -s0x48000000,64M -r -b5 -w4096`**, launches `inic_emergency_script.sh`, `devc-pty`, `random -t`, `challenge -p 22111 -k /stage3/data/challenge.pub &`, and `swdlclient &`.

`/etc/mcd.mnt` (431 B) specifies USB mass-storage matching `/dev/umass[0-9]*` mounted in `/fs/usb%0` as `dos`; it **does not** describe the origin of the system `/stage3` mount. The external network script `/etc/scripts/extnet.sh` defaults to `en0`, uses DHCP iff `/mnt/persist_fpk/use_dhcp` exists, otherwise static `172.16.250.220/24` (subject to override `/mnt/persist_fpk/use_static`). Build label in `/etc/build_version.txt` is `SOP4_AU536_AU491 e.solutions 2018/06/22-15:20`, release `C1_AU736_0378_1280_prod`; `img_ver.txt` contains `232` in both app and stage3. These version and network values are observations, not emulator defaults.

Architecture implication: Stage3 scripts **presuppose** QNX kernel/userland, /stage3 mount, /dev/nvgpio, /config and several /mnt paths. They cannot directly boot on bare AVP. The hard-coded `0x48000000,64M` command gives a concrete flash memory window to investigate in Tegra30 / FPK1 QEMU, but driver options alone do not establish the exact hardware type or bus. Prioritize parsing Stage1/Stage2 boot scripts and mount commands, then hardware dependency mapping and a staged boot plan. Do not run service scripts on host macOS.

## Stage3 script dependencies constrain Stage1/Stage2 boot investigation

Observed `stage3.sh` does **not** establish how Stage3 was mounted: it simply assumes `/stage3/bin/startup-common.sh` and other existing system paths. In turn `startup-common.sh` assumes `/dev/nvgpio/vcm_usb_on1`, `/etc/inetd.conf`, USB rules, and preexisting QNX facilities. Therefore the origin of `/stage3`, `/mnt/temp_fpk`, `/mnt/persist_fpk`, `/config` and the initial `procnto` handoff is a **Stage1/Stage2** problem, not something to solve by executing Stage3 scripts directly in QEMU.

Added `tools/fpk1/probe_early_boot_references.py` to search three early-stage signed FLASHDATA payloads for specific ASCII mount, QNX process, and stage-launch references. It includes exact raw-member offsets, SignInfo-relative offsets and historical candidate-inner offsets, so comparisons do not repeat the old off-by-eight confusion. **This is a read-only string-reference inventory; matches alone do not prove execution or successful decompression.** The output needs to be obtained on the original firmware ZIP before any concrete early-boot call graph can be claimed.

To run on macOS:
```sh
cd /Users/pavelk/workspace/other/qemu-mhi2
git pull --ff-only
python3 tools/fpk1/probe_early_boot_references.py /Users/pavelk/workspace/other/qemu-mhi2/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip --json /tmp/fpk1-early-boot-references.json
```

The existing `tools/fpk1/inspect_stage2_imagefs.py` remains relevant: STAGE2.2's catalog has a verified imagefs directory, but most regular-file data spans exceed the stored extent. **Do not assume that an in-image search absence means a filename or command is absent from the logical Stage2 filesystem** without reconstructing the encoding.

## Stage1 boot references: mount_nand and /stage3 proximity

User-run `probe_early_boot_references.py` reveals Stage1 candidate-inner `mount_nand` at `0x794e0` and `:/stage3` at `0x79542`, separated by only `0x62` bytes. This is the strongest early-stage lead for filesystem preparation, but strings do **not yet establish** an executable boot script or call order. Stage1 also contains `startup-nvidia-tegra3-mm` at `0x109de`, `fs-qnx6` at `0x10e48`, and `# Needs: fs-qnx6` at `0x1765b4`. Stage2 contains a `Dir\":\"/stage3/\"` reference at `0x18859`, likely serialized metadata but still unclassified, and `S_MOUNTPOI` at `0x7a4df`. Stage1 recovery yielded no corresponding printable matches, inconclusive due to suspected encoding/packing.

Added `tools/fpk1/inspect_boot_reference_context.py` for strictly bounded hex + printable-run + little-endian-u32 contexts around these known offsets in Stage1/Stage2. Coordinates are candidate-inner payload `raw[0xc2:]`. The next user run should reveal whether the strings belong to contiguous boot directives, filename metadata, or unrelated binary fragments. Do not claim an established Stage1→Stage3 mount command before the context is examined.

## Stage1 mount_nand vicinity: binary-encoded context, not plain boot script

User-run `inspect_boot_reference_context.py` inspected Stage1 candidate-inner offsets around `0x794e0` and `0x79542`. Nearby ASCII-like runs include `ksh` at `0x794d7`, `mount_nand` at `0x794e0`, `waitfor_eso` at `0x79515`, `PATH=` at `0x79534`, `:/stage3` at `0x79542`, `IPL_CONFIG_DIR=/config` at `0x79558`, and `kdgui_2dmgr` at `0x795c1`. However hex shows extensive interleaved non-printable bytes and near-word fragments such as `mount_nand 2e 20 16 61 43 60`; the area is **not directly readable shell script**. Do not reconstruct a `mount_nand /stage3` command from string proximity. It may be compressed, tokenized, or binary application data: codec and interpretation unknown.

NEXT: identify encoding/block boundaries and map offsets into candidate Stage1 QNX imagefs file spans before assigning these bytes to startup script or loader. Repeat offset conventions: candidate inner = signed FLASHDATA+8 = HSP raw+0xc2. Direct analysis of a byte string is not proof of control flow.

## Stage1 imagefs catalog mapping probe

Added `tools/fpk1/map_stage1_imagefs_references.py` to search the unwrapped primary Stage1 IFS for exact `imagefs\\x04` headers. It validates candidate logical and directory offsets, 16-bit aligned record lengths, file type and name fields, file extents and the terminating entry, using the existing QNX imagefs layout. Only **validated** catalogs are used to assign the observed `ksh`, `mount_nand`, `waitfor_eso`, `:/stage3`, `IPL_CONFIG_DIR=/config` and `kdgui_2dmgr` offsets to a particular file extent or directory region.

**Not yet tested against the original ZIP**. If no valid catalogs are found, that is a bounded negative result, not proof of a specific compression scheme. Earlier Stage1 candidate `imagefs` string at about `0xe530` lacked independent proof it was a valid filesystem header. If an identified regular-file extent extends past the stored bytes, the mapping is metadata-only and the file cannot simply be extracted as contiguous bytes.

Run:
```sh
cd /Users/pavelk/workspace/other/qemu-mhi2
git pull --ff-only
python3 tools/fpk1/map_stage1_imagefs_references.py /Users/pavelk/workspace/other/qemu-mhi2/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip --json /tmp/fpk1-stage1-imagefs-mapping.json
```

## Stage1 ordinary imagefs catalog probe: negative

User executed `map_stage1_imagefs_references.py` against the signed Stage1 primary: **no validated imagefs catalog**. The single exact `imagefs\\x04`-style candidate was at candidate-inner offset `0x10bdd`, rejected for its directory offset; consequently boot references at `0x794d7`, `0x794e0`, `0x79515`, `0x79542`, `0x79558`, `0x795c1` remain unmapped. This invalidates the simple assumption that Stage1 can be parsed as a contiguous Stage2.2-style imagefs starting at that marker. It **does not** prove any specific compression or that QNX filesystem metadata is absent.

Next probe `tools/fpk1/probe_stage1_qnx_headers.py` records bounded raw bytes and u32 values near Stage1's QNX startup signature and `imagefs` markers to identify actual wrapper/header layouts before writing another catalog parser. The candidate-inner offset system remains raw HSP +`0xc2`. No original image material committed.

## Stage1 startup signature: precise field-layout anomaly (QNX standard version vs observed bytes)

New hex supplied by user for Stage1 candidate-inner at `0x808` starts `eb7eff00 01200108 00012800 986ba080`. Standard QNX `struct startup_header` (see https://github.com/markotikvic/QNX-BBB/blob/master/install/usr/include/sys/startup.h ) has 32-bit signature, **16-bit** version at +4, 8-bit flags1 at +6, flags2 at +7, 16-bit header_size at +8, 16-bit machine at +10, 32-bit startup_vaddr at +12. Under that interpretation: signature `0x00ff7eeb`, **version=0x2001 rather than standard 1**, flags1=`0x01`, flags2=`0x08`, header_size=256, machine=`0x28`, startup_vaddr=`0x80a06b98`. This needs investigation: the signature and plausible size/address do not override the version mismatch. The earlier preliminary interpretation that version was 8-bit, flags1 `0x20`, and flags2 `0x01` was not the standard public QNX startup layout.

Added `tools/fpk1/inspect_stage1_startup_header.py` to decode full field values and bounds, corrected its version/flag offsets in follow-up commit. It is **not yet run** on the original ZIP. Compression is not established by the current evidence. Use the result to validate stored size and startup_size, and investigate the variant/possible modified wrapper before deciding on decoding or emulator load addresses.

Also, Stage1 `imagefs` at `0xe530` appears embedded among binary/ASCII name fragments, while `imagefs\\x04` at `0x10bdd` is followed by fields that fail the standard imagefs catalog offset sanity check. Stage1's cleartext `procnto-smp-...` reference is immediately near that second marker. Neither marker yet proves an uncompressed, directly addressable imagefs catalog.

## Stage1 QNX startup signature: standard layout fails validated size constraints

User ran `inspect_stage1_startup_header.py`. Candidate at inner `0x808`: signature `0x00ff7eeb`, version `0x2001` (standard expected 1), header_size 256, machine 40 (ARM), startup_vaddr `0x80a06b98`; other standard-position values include `startup_size=0x400001a1` (~1 GiB), `stored_size=0x04004007` (~64 MiB), `imagefs_size=0xe0084008`, all inconsistent with the 2,060,280-byte candidate inner image. Per the QNX 6.x standard `startup_header`, these fields are invalid as an entire image declaration; the marker may be embedded in a transformed/modified structure or the standard layout may not apply to this context. Do **not** use `candidate_image_base=0x72e`, stored/ram bounds or an inferred compression type from these fields as a QEMU load contract. Sources: https://qnx.com/developers/docs/6.4.0/neutrino/building/load_process.html and https://github.com/markotikvic/QNX-BBB/blob/master/install/usr/include/sys/startup.h .

Updated `inspect_stage1_startup_header.py` to gate computed image base and extent by version and size plausibility and explicitly report validity failures. Next forensic step should characterize the Stage1 transformed/packed data and **seek independent boot metadata**, rather than forcing a standard QNX header decoder onto this sequence. In particular compare the valid ARM jump stub immediately preceding `0x808` to the corrupted/encoded header region, and locate original 0x800 segment container boundaries.

## Stage1 transformed-region boundary comparison

Added `tools/fpk1/probe_stage1_region_layout.py`, a no-decompression, read-only Stage1 primary/recovery comparison across offsets `0x0`, `0x7f0`, `0x800`, `0x808`, `0xe500`, `0x10bc0`, `0x79400` and other checkpoints. It reports entropy, density of zero/FF/ASCII, hashes and first bytes in 256-byte windows, plus aligned windows for block sizes 256..16384 and direct primary-vs-recovery window differences. Its purpose is to identify a structural transition or repeated framing before proposing any codec or relocating QNX startup. **No execution or decoding is claimed.** Run `python3 tools/fpk1/probe_stage1_region_layout.py <firmware.zip> --json /tmp/fpk1-stage1-region-layout.json` then inspect `primary_recovery_windows` and relevant `images.*.windows` rows. Old startup header size fields were invalid under the standard QNX parser; don't reuse those as file offsets.

## Stage1 primary vs recovery data profile (user-run)

The user ran `probe_stage1_region_layout.py`. Stage1 Primary after offset `0x800` contains plausible ARM instructions, QNX marker and mixed printable/binary content; local 256-byte window entropies are broadly 5.4–6.2 bits/byte. An especially notable repeated three-byte sequence is `e0 ff 00` at inner `0x79000` (entropy 1.5849). Stage1 Recovery, despite a mostly shared initial 0x800-byte header, diverges almost completely after 0x800 and has local entropies roughly 7.0–7.2. This **does not prove** Primary uses a particular codec or Recovery is encrypted; the observed entropy windows are too short for that attribution and highly structured byte patterns can have other causes.

New `tools/fpk1/profile_stage1_patterns.py` counts exact runs of `e0ff00` and records 4096-byte-window entropies and ASCII densities across both images, reporting especially the `0x76000–0x82000` range. This is a read-only boundary characterization step before experimenting with any decompression. Next correlate repeated pattern runs with 4 KiB alignment and investigate the source of these bytes (e.g., compressed/code/data representation) without assuming that the ASCII fragments form shell script.

## Stage1 repeated E0 FF 00 runs across primary, not recovery

User-run `profile_stage1_patterns.py`: Stage1 Primary has 503 windows at 4096 bytes, only 3 with entropy >7.5, and 56 contiguous `e0ff00` runs of at least four triplets. Examples: `0x78fa9` 137 triplets (411 bytes), `0x105f13` 240 triplets (720 bytes), `0xea6be` 155 triplets. Recovery has 2135 windows, 2120 >7.5 bits/byte, and **zero** such runs. This confirms a strong distinction in *statistical representation* but neither identifies an encoding/codec nor proves encryption. QNX mkifs supports compressed OS images; public QNX documentation says a bootable image can contain an uncompressed startup segment plus a separately compressed image filesystem. This suggests treating these regions distinctly, but does not establish that these particular samples use that mechanism. References: https://www.get.qnx.com/developers/docs/7.0.0/com.qnx.doc.neutrino.building/topic/buildfiles/nto_bootstrap.html and https://qnx.com/developers/docs/6.5.0SP1.update/com.qnx.doc.neutrino_utilities/m/mkifs.html .

Added `tools/fpk1/inspect_stage1_triplet_runs.py` to measure run-length distribution, start alignment modulo 16/512 and bounded before/after samples for long `e0ff00` runs. This will test whether the token is part of a framed encoding or simply a common byte pattern. It has not yet been executed against the local original ZIP; results must be reviewed before making codec or block-boundary claims.

## Stage1 E0FF00 runs adjacent to apparent ELF headers

User-run `inspect_stage1_triplet_runs.py` found 56 runs totaling 7,506 bytes in Primary and none in Recovery. Nine of the ten longest printed Primary runs were followed by four bytes of the form `e0 XX 00 06` then `7f 45 4c 46` (ELF magic); examples include runs at `0x105f13` (240 triplets), `0x14347f` (187), `0x1ca27f` (172), and `0xea6be` (155). The `0x78fa9` run is an observed counterexample. These fragments may represent structured padding, a transformed file stream or adjacent records, but **do not yet prove a codec, encoding, complete ELF header, or directly runnable program**.

Added `tools/fpk1/correlate_stage1_elf_runs.py`: records all triplet runs and tests for ELF magic within 128 bytes after their end, reporting distance and structural ELF32 ARM header field plausibility. This supplies a falsifiable check of the apparent adjacency and whether ELF signatures correspond to valid headers. Next run on original ZIP, inspect `runs_with_nearby_elf`, `distances_after_run` and `plausible_elf32_arm_header`. No firmware blobs committed.

## ELF correlations with Stage1 repeated-triplet runs

User ran `correlate_stage1_elf_runs.py` against original primary Stage1: 56 runs of `e0ff00` length at least four; **43** have an ELF magic within 128 bytes of their end; distance histogram is `3:3, 4:38, 41:1, 89:1`. All reported raw ELF32/ARM plausibility checks were false. Typical byte sequence after the run is `e0 XX 00 05/06 7f454c46`; apparent ELF `e_machine` includes e.g. 13312 rather than standard ARM e_machine 40. These numbers strongly support a systematic binary representation that retains some ELF magic, but do **not** prove a particular compression codec or that ELF files are intact.

Added `tools/fpk1/analyze_stage1_elf_transforms.py` to inventory **all** Stage1 `7fELF` hits, report the 64 following raw bytes, identification prefixes, version/machine/ehsize in the *untransformed stream*, and any immediately preceding four-byte `e0 XX 00 05/06` marker. This read-only probe is intended to reveal recurring corruption/encoding patterns without inventing a decoder; user should inspect `most_common_ident16` and representative `headers`.

## Important Stage1 decoding breakthrough: likely LZF token stream

User's `analyze_stage1_elf_transforms.py` run found 41 raw ELF magic occurrences in Stage1 Primary, of which 38 have an immediate four-byte `e0 XX 00 05/06` preceding marker. The user previously confirmed 56 `e0ff00` triplet runs, 43 of which sit near ELF magic. **This is a strong match to LZF token grammar**:

- `E0 FF 00`: LZF long backreference with length `(E0>>5=7)+FF+2=264` and distance `(((E0&31)<<8)|00)+1=1`. Consequently it repeats the previous decoded byte 264 times (if the containing stream starts early enough).
- `E0 90 00`: same token with extension `0x90` = 153 bytes repeated at distance 1.
- `06 7F 45 4C 46 01 01 01`: LZF literal-run control `06`, followed by 7 literal bytes beginning an ELF32 header.
- A following `05 7F 45 4C 46 01 01` likewise copies 6 literal bytes.

This coherently explains the invalid *raw* ELF headers: raw bytes contain intermixed LZF control tokens and literal fragments. However **successful complete-stream decompression has not yet been observed**, and the exact stream start/end (possibly independent blocks) are not established. Do not declare the recovered IFS or an ELF executable until decoded bytes validate.

Added `tools/fpk1/probe_stage1_lzf.py`: bounded, in-memory LZF decompressor (64 MiB decoded cap), probes candidate stream starts and checks decoded ELF32 ARM headers and `imagefs\\x04` markers. It does not export proprietary bytes or run the decoded code. If a probe stops due to backreference-before-start or truncated final token, test an independently grounded stream boundary; do not automatically assume whole Stage1 is one LZF stream.

User command:
```sh
cd /Users/pavelk/workspace/other/qemu-mhi2
git pull --ff-only
python3 tools/fpk1/probe_stage1_lzf.py /Users/pavelk/workspace/other/qemu-mhi2/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip --json /tmp/fpk1-stage1-lzf.json
```

## Whole-tail LZF probes failed; isolate token grammar

User ran `probe_stage1_lzf.py` on candidate starts `0x0`, `0x800`, `0x808`, `0x810`, `0x820`, `0x900`, `0x1000`, `0x2000`, `0xe000`, `0xe100`, `0xe500`, and `0x10bc0`; all failed immediately with `backreference before stream start`. These failures reject the simple assumption that each guessed offset is the beginning of a standalone continuous LZF stream; they do not independently disprove local LZF syntax. No original Stage1 contents have yet been successfully decompressed.

Added `tools/fpk1/probe_stage1_lzf_local.py` to test token grammar from known repeated-triplet starts with a deliberately synthetic single zero-byte history and bounded 16-KiB output. Its `plausible_elf32_arm` metric is valuable evidence if positive, but a seeded local decode is **not** proof of actual compressed stream boundaries or correct file bytes. All results are metadata only; no firmware binary saved. Run `python3 tools/fpk1/probe_stage1_lzf_local.py <archive.zip> --json /tmp/fpk1-stage1-lzf-local.json`.

## Stage1 LZF local decoding succeeds on ELF32 headers

User ran `probe_stage1_lzf_local.py`: of 56 repeated-triplet starts, 31 produce decoded `7fELF` magic and 9 produce initially plausible ELF32 little-endian ARM headers (machine=40, version=1, ELF header size=52). Seven particularly useful candidates decode without local backreference error: `0xf1bbb`, `0x112367`, `0x131913`, `0x164d17`, `0x18da01`, `0x19421c`, `0x1c14f8`. Two others (`0x1765ee`, `0x18b4e0`) do produce plausible header fields but the longer local stream later hits a bad backreference.

This substantially strengthens the LZF identification beyond control-token matching; it does **not** yet establish a true stream start, a decompressed filesystem or a complete ELF file, because the local decoder starts with a synthetic one-byte zero history. Added `tools/fpk1/validate_stage1_lzf_elf_segments.py`, which checks decoded ELF program headers (PHDR alignment, type and size, PT_LOAD existence, and available byte extents) within the bounded seed-decoded output. A missing segment due to hitting the bound is inconclusive, not disproof. Use results to prioritize finding actual framing.

## Stage1 LZF decoded ELF program-header validation (user result)

User executed `validate_stage1_lzf_elf_segments.py` against original firmware. Results: **8** decoded ELF candidates have structurally valid ELF32 ARM program headers; **all 8 have two PT_LOAD segments**; **2** have all reported segment file ranges inside the bounded locally decoded buffer. Candidates:

| Original primary candidate-inner start | PHDR valid | PT_LOAD | All PHDR file extents locally present | Local decode error |
| --- | --- | ---: | --- | --- |
| 0xf1bbb | yes | 2 | no | none |
| 0x112367 | yes | 2 | no | none |
| 0x131913 | yes | 2 | yes | none |
| 0x164d17 | yes | 2 | no | none |
| 0x18b4e0 | yes | 2 | no | invalid backreference |
| 0x18da01 | yes | 2 | yes | none |
| 0x19421c | yes | 2 | no | none |
| 0x1c14f8 | yes | 2 | no | none |

This is strong evidence for LZF-compatible **local** encoding. However `all_file_extents_available` covers the segment entries parsed within the bounded seeded decode, not an independent proof of ELF integrity, complete source-file extents, hashes or a valid Stage1 imagefs. A run can begin within a larger compressed stream, and the decoder deliberately inserts a synthetic initial zero byte. **Do not claim an executable has been faithfully recovered or boot original QNX from these bytes yet.**

Next: identify true compressed stream or chunk boundary from container metadata, eliminate synthetic history, then validate ELF program-header contents and file integrity; in parallel revisit the encoded Stage1 `imagefs` catalog. No proprietary bytes committed.

## Search for LZF starts with empty history (following validated local ELF data)

Added `tools/fpk1/find_stage1_lzf_starts.py`: bounded forensic search for a possible *real* LZF stream start in the 2048 bytes before six previously identified ELF-adjacent runs (`0x131913`, `0x18da01`, `0xf1bbb`, `0x112367`, `0x19421c`, `0x1c14f8`). Unlike `probe_stage1_lzf_local.py`, the decoder begins with **empty** output and rejects any backwards reference to unavailable bytes. For each candidate source offset, it requires a decoded complete ELF32 little-endian ARM header, reports candidates and consumes at most 8 MiB output per hypothesis. This is a falsifiable search for stream boundaries, **not** proof of framing: matches can arise from valid LZF suffix parsing starting inside a larger stream. Zero hits is also inconclusive, as true chunk starts might lie farther back and real framing may provide dictionary context.

Run locally:
```sh
cd /Users/pavelk/workspace/other/qemu-mhi2
git pull --ff-only
python3 tools/fpk1/find_stage1_lzf_starts.py /Users/pavelk/workspace/other/qemu-mhi2/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip --json /tmp/fpk1-lzf-boundaries.json
```
Inspect `targets[].valid_candidate_count` and `targets[].candidate_starts`. Preserve the distinction between locally valid ELF structure and authenticated/full-image recovery.

## Empty-history LZF suffix candidate starts (user result)

User executed `find_stage1_lzf_starts.py`, 2048-byte lookback from six selected runs. Four targets have **8 total** starts from which the current LZF grammar decoder reaches an ELF32 ARM header with empty history:

- run `0x131913`: `0x1318fc`, `0x131910`, `0x131911` (decoded 8020, 8001, 8000 bytes)
- run `0x18da01`: `0x18d9fe`, `0x18d9ff` (3769, 3768)
- run `0x19421c`: `0x194216` (10641)
- run `0x1c14f8`: `0x1c14f5`, `0x1c14f6` (7742, 7741)

Targets `0xf1bbb` and `0x112367` yielded none in the tested lookback. These are unseeded decodings, but several candidate offsets are adjacent to the run and **not proven true compression framing boundaries**. Source bytes following the point where the previous probe stops may contain more data, and actual chunk starts could be farther away.

Added `tools/fpk1/validate_stage1_unseeded_lzf.py` to decode forward up to 16 MiB from each of the eight starts, then validate ELF32 ARM program-header tables and the locally available PT_LOAD file extents, reporting stops and output sizes. This is still a suffix test, not authenticated full Stage1 recovery. Run `python3 tools/fpk1/validate_stage1_unseeded_lzf.py <archive.zip> --json /tmp/fpk1-lzf-unseeded-validation.json`.

## Unseeded LZF decoding to physical EOF: multiple valid ELF headers, no complete LOADs

User ran `validate_stage1_unseeded_lzf.py`. All eight suffix candidates decoded until `truncated literal`, with decoded output between 515,052 and 1,634,473 bytes. Depending on start, 2–6 internally plausible ARM ELF32 headers were seen, but **zero** had all PT_LOAD extents present. Example `0x1318fc`: 1,634,473 decoded bytes, six plausible ELF headers and zero complete LOADs; `0x18d9fe`: 910,173 decoded bytes, four ELF headers and zero complete LOADs. The uniform end error indicates that the decoder was fed physical image bytes until its last literal overran EOF; it **does not prove** a true compression block end, nor that the logical ELF file's complete data lives in that suffix. LZF remains strongly supported locally, while genuine stream start/end framing and full-image decoding are open.

Added `tools/fpk1/diagnose_stage1_lzf_extents.py` to report the exact compressed stopping position, physical remaining bytes, decoded ELF positions, largest PT_LOAD file-end offset, and the gap between each required extent and the available suffix length. This should discriminate between genuinely missing decoded data and misinterpreted segment-size fields. Run against user's original ZIP; no proprietary binary is written.

## LZF suffixes: segment extents available, but program-header sizes invalid

User ran `diagnose_stage1_lzf_extents.py` on all eight unseeded candidate starts. All stop at encoded candidate-inner `0x1f6ffc` with `truncated literal`, i.e., the physical end of the supplied candidate bytes, **not independently verified LZF framing**. Crucially the diagnostic showed `missing_bytes_for_max_load_end=0` for every reported ELF. The first ELF from start `0x1318fc` has `available_from_elf=1628277` versus `max_load_file_end=8908`. However **all candidates report `all_pt_load_size_ok=False`**; additionally many parsed ELF headers have `max_load_file_end=0`, suggesting zero PT_LOAD count or other invalid program entries. Thus the lack of complete ELF is **not** due to missing bytes per these raw fields. Our earlier shorthand "complete LOAD extents" was misleading because the conjunction included `p_filesz<=p_memsz`. Need to inspect individual PHDR values, distinguish `PT_LOAD` from other PHDR types, and avoid calling these full ELF files.

Added `tools/fpk1/inspect_stage1_lzf_phdr_values.py` to report individual decoded ELF program-header types, file offsets, file sizes, memory sizes, flags and alignment, while preserving the empty-history suffix caveat. This should determine whether values imply wrong LZF decoding, misaligned ELF extraction, or a different representation. Run on original ZIP and inspect first candidate with PT_LOAD and other entries. Do not claim full IFS reconstruction.

## Correction: previously counted "valid ELF" were only shallow-header matches

User supplied full `inspect_stage1_lzf_phdr_values.py` output (eight unseeded candidate starts). Actual program headers are structurally inconsistent despite ELF32/ARM identification bytes:

- For suffix `0x1318fc`, decoded ELF at `0x1834`, first `PT_LOAD` has `p_filesz=8908`, `p_memsz=261`, and `p_align=0x20003`. This violates ELF load-segment semantics and alignment; subsequent entries have unknown types and huge values.
- For suffix `0x18d9fe`, ELF at `0x61fa2` has `PT_PHDR` but **no trustworthy PT_LOAD entries** among the displayed records. A `PT_INTERP` row has `p_filesz=20`, `p_memsz=5`, but `p_filesz<=p_memsz` is a mandatory constraint for **PT_LOAD**, not all program-header types; avoid applying that heuristic universally.
- Some apparent segments have path-fragment-like numerical values (`0x7273752f`, `0x71646c2f`) and implausible alignment. This points to a mislocated ELF header or misdecoded source bytes, not a complete ELF.

**Correction:** previous counters of 8 plausible ELF32 ARM program headers and 8/8 with two PT_LOAD refer to earlier, weaker, non-independent checks, and do **not** establish eight valid ELF files. An unseeded LZF suffix can contain recognizable ELF-looking fragments while the table is unusable. Full Stage1 has not been decoded.

Updated `tools/fpk1/validate_stage1_unseeded_lzf.py` to require meaningful program-header types, at least one PT_LOAD, PT_LOAD file-size/memory-size ordering and alignment congruence, and present file extents, recording reasons under `strict_valid_elf_count` and `rejection_reasons`. The next step is to determine actual LZF framing and byte alignment before trusting file catalogs or QEMU load addresses.

## Zero candidates after strict ELF validation: identify overfiltering

User ran updated `validate_stage1_unseeded_lzf.py`: all eight empty-history suffix starts reported `elf_valid_count=0` and `strict_valid_elf_count=0`. Inspection showed the new preliminary check required `e_ident[7:16]` to be all zero, which is too aggressive for forensic discovery and can discard partly damaged/non-standard QNX headers before reporting the PHDR defects. Fixed this in `a782d94`: nonzero identification tail is a **diagnostic reason**, while the core header match and semantic PHDR checks are distinct. The result remains **no proven recovered ELF**; the user should rerun and inspect the rejection reasons rather than treating 0 discovered candidates as definitive evidence against LZF.

Prior PHDR dumps independently show impossible PT_LOAD sizes and unknown segment types, so accepting a shallow header is still not enough for successful validation.

## Fixed regression: ELF magic scanner accidentally searched literal backslash sequences

User reran the stricter `validate_stage1_unseeded_lzf.py` against all eight candidate starts: every output reported `elf_valid_count=0`, `strict_valid_elf_count=0` and empty `elfs`, despite older diagnostics finding several ELF magic offsets in the *same decoded outputs*. Root cause identified in the script's prior edit: the scanner contained Python byte literals spelled `b"\\\\x7fELF"` / `b"\\\\x01"`, which match literal backslash characters rather than actual ELF magic bytes. Thus the zero count was a **validator regression**, not new forensic evidence about firmware.

Commit `a8fd13a` restores actual escape sequences `b"\\x7fELF"` and `b"\\x01"` and adds a separate `elf_magic_count` counter. The overrestrictive nine-byte all-zero `e_ident` tail requirement is also removed from the preliminary filter (still logged diagnostically). **No original ZIP rerun after this fix has been reviewed yet**. The independently observed invalid program-segment types and `p_filesz>p_memsz` examples remain genuine reasons for skepticism, regardless of scan bug. Rerun the script and inspect `elf_magic_count`, `elf_valid_count` and per-candidate `rejection_reasons` before drawing any further conclusions.

## Strict decoded-ELF failure confirmed across all eight candidate LZF suffixes

User reran corrected `validate_stage1_unseeded_lzf.py`. Counts by start: `0x1318fc`, `0x131910`, `0x131911` each 39 raw decoded ELF magic, 6 shallow candidates, **0 strict**; `0x18d9fe`/`0x18d9ff` each 29/4/0; `0x194216` 26/3/0; `0x1c14f5`/`0x1c14f6` each 15/2/0. Rejection details repeatedly identify invalid PT_LOAD semantics (`invalid_PT_LOAD:0`), impossible or unknown PHDR types (`0x22cc`, `0x70000001`, `0x280034`), out-of-bounds PHDR extents, and often `no_PT_LOAD`. The same logical candidate content appears from slightly different decoder starts, shifted by small offsets; these are not eight independent recovered files.

Conclusion: LZF-compatible token grammar is strongly supported, but no recovered *valid ELF32 ARM executable* and no verified complete Stage1 imagefs. **Do not characterize shallow decoded header matches as valid executables or QEMU boot assets.** Avoid searching more arbitrary suffix offsets as the principal next step. Instead identify codec stream framing/starting state from the original image container and check whether the decoded bytes represent a transformed or packed IFS representation. A successful independent LZF decoder test plus comparison to known valid ELF/IFS format should precede boot experiments.

## LZF decoder correctness gate: synthetic fixture tests

Added `tools/fpk1/test_lzf_decoders.py`, a firmware-independent `unittest` suite covering literal runs including ELF-prefix bytes, LZF match distances 1/2/4, overlapping and non-overlapping backreferences, extended 264-byte `e0ff00` matches, repeated long matches, invalid backward references, truncated literals and decoded-size caps. For every success case, compares `probe_stage1_lzf.decode` to `validate_stage1_unseeded_lzf.decode` on the same synthetic wire bytes; for error cases checks explicit failure behavior. These are implementation checks, **not** independent third-party LZF vectors or proof that FPK1 Stage1 uses standalone LZF framing. The test suite is not yet claimed to have run in GitHub CI.

Run from the repository root:
```sh
python3 -m unittest discover -s tools/fpk1 -p 'test_lzf_decoders.py' -v
```
If fixtures pass but strict ELF checks stay zero, prioritize the encoded-data framing, possible dictionary reset/data chunk boundaries or outer container interpretation over adjusting the ELF validator to accept invalid PHDRs.

## LZF decoder bug exposed by firmware-free regression test

User ran the 10 synthetic `test_lzf_decoders.py` fixtures on macOS: nine passed, but `test_nonoverlap_reference` failed: encoded `03 41 42 43 44 40 03` should decode `ABCDABCD` and incorrectly returned `ABCD`. Root cause in **both** decoders: the optimized case `distance >= length` used `out[-distance:-distance+n]`; when `distance==length`, this is `out[-4:0]` (empty), and some unequal cases truncate as well due to Python's negative/zero slicing semantics.

Fixed the two implementations (`probe_stage1_lzf.py` and `validate_stage1_unseeded_lzf.py`) to slice from an explicit positive index `len(out)-distance` to `len(out)-distance+n`, and added regression fixtures for `distance>length` and `distance==length`. The previous Stage1 LZF decoded ELF counts, segment validity findings, and compression-to-EOF sizes **must be recomputed** after this decoder correction: decoded offsets may have shifted and bytes may be missing from earlier outputs. Do not rely on the previous 'all strict ELF invalid' verdict as final until rerun.

Reproduce fixture suite:
```sh
python3 -m unittest discover -s tools/fpk1 -p 'test_lzf_decoders.py' -v
```
Then rerun `validate_stage1_unseeded_lzf.py` on original archive. Tests and reruns not yet confirmed on the user's Mac after this change.

## Corrected LZF decoder yields structurally valid Stage1 ARM ELF segments

After the nonoverlap/equal-distance backreference slicing fix, user reran `validate_stage1_unseeded_lzf.py`. **Major positive result**:
- unseeded starts `0x1318fc`, `0x131910`, `0x131911`: decoded 1,638,062 / 1,638,043 / 1,638,042 bytes; 30 preliminary ELF candidates each, **24 strict-valid** each;
- `0x18d9fe`, `0x18d9ff`: 912,204 / 912,203 decoded; 21 candidate, **18 strict-valid**;
- `0x194216`: 858,160 decoded; 18 candidate, **15 strict-valid**;
- `0x1c14f5`, `0x1c14f6`: 515,896 / 515,895 decoded; 10 candidate, **9 strict-valid**.

These sets overlap in compressed-source coordinates and are NOT 24+18+15+9 unique files. They demonstrate genuine, repeatable LZF decoding of many structural ARM ELF headers and PHDR extents; previous corrupted-PHDR reports arose at least in substantial part from the decoder's negative-index slicing bug.

All starts still terminate with `truncated literal` at physical candidate-inner EOF, so neither actual compressed stream boundary nor complete unwrapped imagefs has been established. Next prioritize mapping the reconstructed stream to logical imagefs metadata/file names and finding the original chunk/stream start, with bounded data checks and no proprietary binary commits. The Stage1 QNX startup header's standard-layout mismatch also remains unresolved; do not infer boot entry or image base from those invalid size fields.

## Inspect decoded Stage1 LZF suffix for imagefs records

Added `tools/fpk1/inspect_decoded_stage1_imagefs.py`: decode in memory from a candidate Stage1 source offset (default `0x1318fc`, currently yielding 24 structurally validated ARM ELF candidates with the fixed decoder), search the **decoded** byte stream for `imagefs\\x04`, and apply QNX imagefs catalog constraints (header extents, 16-bit record boundaries, file names, regular-file extents, terminating record). It also reports compressed-source EOF/error and the number of strict ELF hits in that same decoded output. No proprietary binary is written. The script has **not yet been run against the original archive**, and presence/absence of the catalog in a suffix is not conclusive about the full logical Stage1 IFS.

Run:
```sh
cd /Users/pavelk/workspace/other/qemu-mhi2
git pull --ff-only
python3 tools/fpk1/inspect_decoded_stage1_imagefs.py AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip --json /tmp/fpk1-stage1-decoded-imagefs.json
```
Priority next: identify true stream framing and the missing leading portion of the compressed image before booting the decoded startup/ELF.

## Decoded Stage1 suffix: no imagefs marker, EOF only four bytes after token error

User ran `inspect_decoded_stage1_imagefs.py` from `0x1318fc`. Decoded size 1,638,062; 30 shallow ARM ELF candidates, 24 strict-valid; decoded `imagefs` text matches **zero**. Last consumed encoded position `0x1f6ffc` vs candidate inner length `0x1f7000`, four bytes remaining, failure `truncated literal`. Last consumed raw bytes: `...00006865500e`. This does not show where the failed token **begins**: `encoded_stop` is the pointer after reading its control byte. Do not assume `0x0e` is necessarily the failing control without tracing the token boundary. If it is, the decoder asks for fifteen literal bytes, but only four remain; physical EOF is not a verified end-of-stream marker.

Added `tools/fpk1/trace_stage1_lzf_tail.py` to report exact failed-token start/control, last fully decoded token boundary, physical last nonzero byte, decoded output count, and nearby token boundaries from several valid candidate starts. The script traces lengths rather than allocating the entire decoded output and does not export firmware data. Run `python3 tools/fpk1/trace_stage1_lzf_tail.py <archive.zip> --json /tmp/fpk1-lzf-tail.json`.

The lack of decoded imagefs text in an LZF *suffix* says nothing conclusive about imagefs in the missing earlier portion. The next stage remains true compression block start/end recovery.

## Stage1 LZF end boundary traced consistently

User ran `trace_stage1_lzf_tail.py` on original image. Four suffix decodings from `0x1318fc`, `0x18d9fe`, `0x194216`, `0x1c14f5` agree: last complete token ends at `0x1f6ffb`, next token begins at `0x1f6ffb` with control `0x0e` (15 literal bytes required), and EOF is `0x1f7000`. Last nonzero byte is `0x1f6ffc`. The four sources share their later compressed suffix, so this agreement confirms decoder convergence, *not* independent framing evidence. A candidate encoded block endpoint is `0x1f6ffb`, leaving five bytes `[0x1f6ffb:0x1f7000]`; contents/meaning are still unverified. An explicit bounded decoder test against `0x1f6ffb` and header-length cross-check are next.

## Explicit-end Stage1 LZF check confirms clean suffix (original user run)

User ran `check_stage1_lzf_endpoint.py` on the primary Stage1 member. Candidate-inner length `0x1f7000`, bounded suffix end `0x1f6ffb`, trailer five bytes `0e01000000`. Empty-history decoding from four candidate starts terminates exactly at `0x1f6ffb` with `error=null`: 24/30 strict/shallow ELF matches at start `0x1318fc`, 18/21 from `0x18d9fe`, 15/18 from `0x194216`, 9/10 from `0x1c14f5`. The shared suffixes are overlapping, not disjoint. Inner first LE word `0x1f656c` differs from physical size `0x1f7000` by `0xa94`. The trailer's trailing four bytes read as LE 1, but this is an unverified interpretation. **A clean decode to a chosen endpoint confirms an LZF token boundary, not the original compression framing or IFS layout.** Decoded imagefs marker remains absent in this suffix.

Added `tools/fpk1/inspect_stage1_length_fields.py` to expose the full HSP wrapper prefix, first inner 256 bytes, trailing 64 bytes, and correlations of selected size values with early header words. Header bytes are user-local only; do not commit the proprietary payload.

## Stage1 size correlation

User output: HSP member 0x1f70c2 bytes; inner payload 0x1f7000 bytes, matching two HSP length words at raw offsets 0x10 and 0x14. Inner first word 0x1f656c differs by 0xa94 bytes. Clean LZF suffix token boundary is 0x1f6ffb, followed by 0e01000000. Meaning of that trailer and first word remain unverified. Early inner header contains boot arguments with serial console configuration. Prioritize decoding header layout and true LZF block framing.

## Stage1 early boot header and ARM startup inspection

User observed initial header: inner +0x0 = 0x1f656c, +0x4 = 0x00a00800, +0x1c = 0x800, +0x258 = 2, +0x3f8 = 0xe8. Nonzero entries around +0x7f4..+0x7fc need contextual analysis. ASCII arguments at +0x38 include a serial-console parameter. Inner +0x800 starts with 0cc08fe2 00f09ce5, ARM little-endian boot stub, immediately followed by the familiar QNX-related signature eb7eff00. These observations corroborate the +0x800 transition to code, not to the first LZF token or necessarily to the entire QNX startup header.

Added `tools/fpk1/inspect_stage1_startup_region.py` to report early ARM words in a user-configurable window and exact occurrence offsets for QNX markers. This is a preparatory raw-evidence step; true compression framing and IFS catalog remain unverified.

## Stage1 ARM stub direct branch interpretation

User-local startup probe shows inner +0x800 LE word 0xe28fc00c (ARM ADD ip, pc, #12), +0x804 0xe59cf000 (LDR pc, [ip]), and +0x814 0x80a06b98. Under ARM-state PC+8 semantics, the first instruction takes ip = instruction_address(+0x800)+8+12 = +0x814 and the second loads PC from that literal word. Thus 0x80a06b98 is a candidate physical/virtual branch target **provided the stub is executed in ARM state at its intended mapping**. +0x81c is 0x80a00808, plausibly an address relationship to the startup header at inner +0x808, but a mapping is not yet validated. qnx_magic +0x808, startup-nvidia-tegra3-mm at +0x109de, imagefs strings at +0xe530 and +0x10bdd. Do not conflate magic-string occurrences with validated file catalog offsets.

Added `tools/fpk1/inspect_stage1_arm_entry.py` to calculate target and test explicit candidate memory bases against image offsets. Its candidates are hypotheses, not boot configuration.

## Stage1 candidate load base inferred from startup pointer

User provided Stage1 ARM stub pointer at inner +0x814 = 0x80a06b98 and QNX-related header pointer at +0x81c = 0x80a00808. Since the QNX magic is at inner +0x808, the latter exactly matches an image loaded at base 0x80a00000. Under that mapping the ARM stub at +0x800 becomes 0x80a00800 and its literal branch target corresponds to inner +0x6b98. This is a coherent placement hypothesis; neither actual execution, memory controller setup, nor QEMU feasibility are yet established.

Added `tools/fpk1/inspect_stage1_entry_code.py` to report bytes and raw words around this target and optionally disassemble them as ARM little-endian if Capstone is installed. This is read-only and does not export firmware. The direct entry-point bytes should be evaluated before treating the hypothesized mapping as proven.

## Raw Stage1 entry mapping unresolved

User confirms base-hypothesis arithmetic: 0x80a06b98 - 0x80a00000 = inner +0x6b98; header pointer 0x80a00808 matches the QNX signature at +0x808. However raw words at +0x6b98 start 0xdb400202, 0xfb21d72f, 0xe5674003, 0x021b20c7, which do not resemble a confident ARM startup entry sequence. It remains possible the target refers to a relocated/uncompressed logical image, or that the interpretation of stub/header is incomplete. Do not mark this as executable code or wire it as QEMU PC without a real disassembly and mapping proof.

Added tools/fpk1/check_stage1_entry_mapping.py for cautious numeric ARM condition-code/branch-pattern comparisons between raw entry region and decoded suffix, explicitly noting that suffix offsets cannot be mapped directly to original offsets without container framing.

## Stage1 ELF entrypoint checks after corrected LZF

User ran `map_stage1_decoded_elf_entries.py`: for LZF suffix start 0x1318fc, 24 strict ARM ELF candidates, all 24 entry addresses fall within a PT_LOAD range; for 0x18d9fe, 18 strict candidates, all 18 map to PT_LOAD. This is additional internal consistency evidence but not proof of execution or independent files (suffix sets overlap). Sample entry values include 0xba8, 0xb18, 0x447c, 0x100f2c, 0x100ecc and 0x101728. These resemble typical per-executable entry VAs and must not be confused with early image startup target 0x80a06b98. Added `tools/fpk1/inventory_stage1_decoded_elf.py` for read-only ELF type, PT_LOAD, entry file offset, byte prefix and surrounding filename clue inventory. Filename clues are not authenticated path catalog entries.

## Read-only decoded Stage1 ELF dependency inventory

User confirmed 24 structural ARM ELF candidates in the corrected Stage1 LZF suffix (four ET_DYN and twenty ET_EXEC, each with two PT_LOAD segments). Added `tools/fpk1/identify_stage1_elf_dependencies.py` to collect ELF type, entry, PT_INTERP and the DT_NEEDED/DT_SONAME/DT_RPATH/DT_RUNPATH names by translating DT_STRTAB virtual addresses using PT_LOAD mappings. The tool reads the local firmware ZIP, decodes only the known bounded suffix in memory, and writes JSON metadata only. String values found in dynamic metadata are not a verified imagefs catalog or file path. Added firmware-independent synthetic tests `tools/fpk1/test_identify_stage1_elf_dependencies.py` for PT_INTERP, DT_NEEDED, DT_SONAME and absent DT_STRTAB.

Run: `python3 -m unittest discover -s tools/fpk1 -p 'test_identify_stage1_elf_dependencies.py' -v` and `python3 tools/fpk1/identify_stage1_elf_dependencies.py <firmware.zip> --json /tmp/fpk1-elf-dependencies.json`. Actual local firmware and test results must be confirmed by the user.

## Decoded Stage1 ELF dynamic identities confirmed from user run

The 24 structurally valid ELF objects decode as four ET_DYN plus twenty ET_EXEC. ET_DYN SONAME metadata: decoded +0x1834 `libnvnordma.so` (needs libc.so.3), +0x5834 `libnvmnand.so` (needs libm.so.2/libc.so.3), +0x6421a `cam-disk.so` (needs libcam.so.2/libc.so.3), and +0xf834 with no recorded SONAME/NEEDED. Every reported ET_EXEC has PT_INTERP `/usr/lib/ldqnx.so.2`; many depend on libc.so.3. Notable ET_EXEC dependencies: +0x11069b needs libnvdisp.so/libnvhost.so/libnvmap.so/libc.so.3; +0x1137a8 libnvsku.so/libc.so.3; +0x1187a8 libnvclockapi_impl.so/libc.so.3; +0x1854f3 libnvclockapi.so/libnvsku.so/libm.so.2/libc.so.3; +0x18b4f3 libnvclockapi.so/libnvsku.so/libc.so.3. These dependents' executable filenames remain UNKNOWN. DT_NEEDED indicates dependency names, not that each dependency was itself recovered. The ELF objects overlap within one LZF suffix; 24 is not a full catalog count. Next probe neighboring decoded bytes for plausible QNX imagefs inode records or names, and compare recovered SONAME/NEEDED against available Stage3 paths.

## Recovered Stage1 ELF-to-path proximity probe

Added `tools/fpk1/correlate_stage1_elf_names.py`. It decodes the known bounded LZF suffix in memory and, for every strict-valid ELF, computes an inferred file-end from ELF program-header file spans. It reports plausible ASCII path-like strings within 512 decoded bytes preceding the ELF magic and following its inferred extent, plus distances to adjacent ELF starts. This is expressly a heuristic proximity inventory, NOT a reconstructed or authenticated QNX imagefs catalog. Its output must not be interpreted as verified filenames. The main open problem remains recovery of the missing imagefs directory/framing and logical file boundaries. Added `test_correlate_stage1_elf_names.py` for text pattern and coordinate checks; execution against firmware and tests is not yet confirmed.

Run `python3 -m unittest discover -s tools/fpk1 -p 'test_correlate_stage1_elf_names.py' -v` and `python3 tools/fpk1/correlate_stage1_elf_names.py <firmware.zip> --json /tmp/fpk1-elf-path-clues.json`.

## Stage1 adjacent path clues proved inconclusive; map compressed coordinates next

User ran the decoded-path proximity tool: only ELF +0x1834 and +0x5834 yielded matching library strings (`libnvnordma.so` and `libnvmnand.so`), both already known from ELF SONAME metadata. Other hits were date-like strings (e.g. 2012/06/20-13, 2015/10/07-10) and `dev/ser`, insufficient to establish ELF filenames. Gaps between inferred ELF file end and next ELF magic range from several thousand to hundreds of thousands of decoded bytes; ELF adjacency is not a reliable imagefs file boundary. Do not present these strings as authenticated catalog names.

Added `tools/fpk1/map_stage1_lzf_elf_offsets.py` to trace LZF tokens from candidate start 0x1318fc to bounded end 0x1f6ffb and map all strict decoded ELF starts back to their containing compressed token positions. It cross-checks traced decoded byte count with the actual fixed decoder. This offers an encoded/decoded coordinate map for studying potential framing or metadata but does not itself identify chunk boundaries or filenames. Tests on the real local ZIP remain to be run by the user.

## Encoded LZF token mapping for all 24 ELF headers

User ran `map_stage1_lzf_elf_offsets.py`: traced 313,450 LZF tokens between inner +0x1318fc and +0x1f6ffb, mapped all 24 strict-valid ELF starts. All 24 decoded ELF starts coincide with the start of an LZF decoded token (`within_decoded_token=0`), 23 on literal tokens and one (ELF decoded +0x1217a8, encoded +0x1c6f59) on a reference token. Every encoded pre-ELF region shows repeated `e0ff00` backreference tokens with a shorter final e0..00-like token, consistent with repeated-byte padding. However, LZF token boundaries are not proof of a filesystem file boundary, and one ELF header begins on a backreference, so there is no proven literal ELF start delimiter. Added `tools/fpk1/measure_stage1_elf_padding.py` to count decoded zero bytes immediately preceding each strict ELF and report alignments in decoded-suffix coordinates. This is a test of the padding hypothesis, not a recovered imagefs catalog.

## Repeated 272–282 byte gaps between PHDR extents and next zero-fill

User output from `analyze_stage1_elf_padding_layout.py` shows recurring small gaps from prior ELF PHDR-derived file-end to zero-run preceding next ELF: 277, 276, 282, 272, 273, 272, 274, 275 bytes at several transitions. Other gaps reach hundreds of kilobytes. Repeated small gaps could be unrelated ELF section-table content or another structure; they are NOT proven imagefs metadata. Adjacent ELF starts sometimes differ by exact 4 KiB multiples, but the coordinate origin is an arbitrary decoded LZF suffix. Added `tools/fpk1/check_stage1_elf_gap_sections.py` to inspect ELF section-table boundaries and non-NOBITS section extents, compare them against PHDR-derived ends, and report SHA-256 prefixes for small gaps. This is a diagnostic, not file extraction or a confirmed container layout. Run on the original ZIP and inspect section extent difference and small-gap hashes.

## Repeated 272-byte gaps explained by ELF section tails (provisional)

User ran `check_stage1_elf_gap_sections.py` for eight small-gap transitions. For every transition, the inferred section data/table end lies exactly one byte beyond the beginning of the zero-run leading to the next ELF: gap vs section-extension values 277/278, 276/277, 282/283, 272/273, 273/274, 272/273, 274/275 and 275/276. Thus these gaps appear to be ordinary ELF section tails rather than separate imagefs record headers. The +1 suggests that the backwards zero-run detector includes the final zero byte of the ELF, but this remains a hypothesis until adjacent bytes and section-table entries are inspected. Added `tools/fpk1/verify_stage1_elf_section_tails.py` to report section-end and zero-run boundary difference, trailing and next byte, and final section records. This is not complete file boundary recovery.

## Decoded ELF section tails confirmed and extent map added

User provided twelve comparisons from `verify_stage1_elf_section_tails.py`: every reported section extent ends exactly one byte after the beginning of the following backward-scanned zero run (`difference=1`); both the last byte at the section extent and first subsequent byte are `0x00`. This supports the explanation that recurring 272–282 byte gaps after PT_LOAD are ELF section content rather than stand-alone filesystem record headers. However, other nonzero content may exist between ELF objects and the full imagefs catalog remains unknown.

Added `tools/fpk1/map_stage1_decoded_regions.py` to summarize all strict ELF extents using program headers and section headers, map gaps to the next ELF, and count unexplained nonzero bytes in each gap. Only JSON metadata is emitted; no firmware binaries are written. This should prioritize which inter-object regions warrant further reverse engineering. No real-firmware run has yet been performed for this new script.

## Bounded section extent fix after decoded region-map output

User ran the region mapper and found four impossible inferred ELF sizes: suffix-local +0xf834 ~1.94 GiB, +0x1217a8 ~2.19 MiB, +0x131964 ~541 MiB, and +0x1723d3 ~2.11 MiB. These are not valid recovered file sizes: the earlier mapper accepted unbounded section offsets even though only ~1.64 MiB of decoded suffix exists. It also exposed significant unexplained nonzero regions following some valid ELF segment extents, particularly +0x6421a (74131 nonzero bytes), +0x88843 (92023), +0xbbb8e (171174) and +0xf94a0 (28196). Such regions are not necessarily additional files; previous ELF extent checks may undercount genuine content.

Fixed `tools/fpk1/map_stage1_decoded_regions.py` to reject out-of-bounds section extents, report `section_issue`, and fall back to program-header-derived extents when section tables cannot be used. The field `minimum_file_bytes` is now nullable when even the fallback overlaps the next candidate. No full imagefs catalog or complete extraction has been validated. Re-run on the original local archive before relying on inferred sizes.

## Corrected Stage1 decoded region map: unexplained nonzero gaps

User reran bounded region mapper. Significant nonzero areas after strict ELF offsets: +0xbbb8e (171174 nonzero/225058 gap), +0x88843 (92023/138457), +0x131964 (77907/164799; section invalid), +0x6421a (74131/134745), +0xf94a0 (28196/46875). These are counts of bytes between inferred file extents, NOT verified distinct files. Other smaller regions also contain nonzero bytes. Three ELF objects (+0x1217a8, +0x131964, +0x1723d3) have section_extent_out_of_bounds, requiring separate review.

Added `tools/fpk1/classify_stage1_unknown_regions.py` to classify those gaps by entropy, ASCII text and signature occurrence counts, emitting JSON metadata only. It reuses the bounded region map; markers inside a gap are clues and cannot identify files independently. Run against original ZIP locally and inspect highest-nonzero regions.

## QNX build metadata discovered in Stage1 decoded ELF/gap areas

User ran `classify_stage1_unknown_regions.py`. Significant meaningful strings occur in previously unexplained regions: after ELF +0xf834: `NAME=libcam.so`, `DESCRIPTION=Generic CAM library`, date 2015/10/07, `STATE=stable`; after +0x131964: `NAME=deva-nvaudio`, 2017-09-25 build metadata; after +0x1723d3: `NAME=devc-ser8250-tegra2`, `DESCRIPTION=Character device driver for the 8250 chipset`; after +0x1217a8: `NAME=i2c-tegra2`, `DESCRIPTION=Tegra2 I2C Driver`. Other regions feature flash symbols (`initialize_flash_dma`, `init_flash_params`) and mount messages. These findings indicate some supposed gaps contain ELF text, build metadata or data beyond the PHDR-derived minimum extent. The NAME strings are concrete, but ownership of a specific preceding ELF remains a proximity hypothesis until validated using section and filename metadata.

Added `tools/fpk1/index_stage1_qnx_build_metadata.py` to scan all decoded bytes for QNX NAME/DESCRIPTION/DATE/STATE/HOST/USER metadata and report proximity to the preceding ELF, plus candidates for names. This does not claim filesystem catalog recovery. User should execute locally and inspect all 24 mappings.

## Stage1 decoded QNX build-name inventory (user-verified strings)

User ran `index_stage1_qnx_build_metadata.py`: 148 build metadata records, 23 of 24 strict ARM ELF candidates have a proximal `NAME=` field. Mapping is **proximity-based**; do not report the names as authenticated imagefs catalog file paths or as proven ELF ownership.

| Decoded ELF offset | Proximal NAME= |
| --- | --- |
| 0x1834 | libnvnordma.so |
| 0x5834 | libnvmnand.so |
| 0xf834 | libcam.so |
| 0x6421a | cam-disk.so |
| 0x88843 | tinit |
| 0xaca81 | mount |
| 0xb1b8e | slogger |
| 0xb5b8e | pipe |
| 0xbbb8e | ksh |
| 0xf54a0 | devg-nvbootprofiler |
| 0xf94a0 | bootprofiler |
| 0x10569b | nvmemctrl |
| 0x10869b | devg-nvsku |
| 0x10c69b | devg-nvos |
| 0x11069b | devg-nvrm |
| 0x1137a8 | devg-nvgpio |
| 0x1187a8 | devg-nvclock |
| 0x11f7a8 | (no NAME= found) |
| 0x1217a8 | i2c-tegra2 |
| 0x131964 | deva-nvaudio |
| 0x1723d3 | devc-ser8250-tegra2 |
| 0x1854f3 | i2s_init |
| 0x1884f3 | display_init |
| 0x18b4f3 | clock_init |

Multiple DESCRIPTION strings occur in proximity windows: e.g. `libcam.so` also sees "Generic filesystem support library"; `cam-disk.so` also sees "QNX6 filesystem library"; `tinit` also sees "Process crash dump file creation daemon"; `deva-nvaudio` also sees "mmc/sd disk driver". These additional DESCRIPTION strings **must not** be attributed to the closest NAME without establishing metadata-record boundaries. They imply additional components/build records or metadata bleed across multiple objects.

Next priority: parse bounded build-record clusters anchored at NAME= and stop at the next NAME= or ELF start, report unassociated records separately, and correlate with validated SONAME/DT_NEEDED without inferring QNX imagefs names.

## Build-record clustering probe

Added `tools/fpk1/cluster_stage1_qnx_build_records.py`, a stricter complement to the original 148-field proximity index. It searches for NUL-bounded `NAME=` records and attempts to collect adjacent NUL-delimited `DESCRIPTION`, `DATE`, `STATE`, `HOST`, `USER` values until a non-field, blank terminator, or next record. Unlike the old field-level grouping, it reports each `NAME` record separately even when multiple records occur between two ELF headers. `names_by_preceding_elf` remains explicitly heuristic and is not a proven association, filesystem path, or catalog. Added firmware-independent synthetic tests `test_cluster_stage1_qnx_build_records.py`; they have not been executed on the user's local image in this session.

Run: `python3 -m unittest discover -s tools/fpk1 -p 'test_cluster_stage1_qnx_build_records.py' -v` then `python3 tools/fpk1/cluster_stage1_qnx_build_records.py <firmware.zip> --json /tmp/fpk1-build-records.json`.

## Build-record parser regression: all 24 groups empty

User reported all 24 `names_by_preceding_elf` empty after running `cluster_stage1_qnx_build_records.py`, despite previous proven NAME string matches. The clustering parser had required every `NAME=` to be immediately preceded by NUL/start, an unsupported assumption for QNX build-information strings with possible printable prefixes. Removed that left-boundary restriction while retaining a NUL-terminated right boundary; updated synthetic regression test for prefixed NAME. This is a parser fix, not evidence that Stage1 has no NAME fields. Need rerun on original firmware and evaluate if inter-field grouping is still overly strict.

## Second build-record parsing failure and fix

User reported `Records: 0` a second time, after removal of the left NUL requirement. The former parser also required each `NAME=` to end at a NUL terminator, whereas the earlier loose regular-expression index successfully extracted NAME fields from these bytes. Replaced the record scan with the same loose field grammar as the previously successful metadata probe (`NAME|DESCRIPTION|DATE|STATE|HOST|USER` followed by printable ASCII), assigning fields to a provisional record from each NAME until next NAME, subject to a 4096-byte gap cutoff. No NUL framing or authentic binary record boundaries are claimed; overlapping/adjacent field ownership remains uncertain. Updated unit tests to cover newline-separated and NUL-separated synthetic cases. Real firmware run pending.

## Stage1 build-record grouping: 27 NAME records across 24 ELF signatures

User reran the corrected clustering probe. It recovered **27 build-info NAME records**, compared with **24 strict ELF signatures**. Four ELF-to-next-ELF windows have two NAME records, and one window has none.

Additional records absent from the earlier one-name-per-ELF summary:
- decoded ELF +0xf834: `libcam.so`, `io-blk.so`
- decoded ELF +0x6421a: `cam-disk.so`, `fs-qnx6.so`
- decoded ELF +0x88843: `tinit`, `dumper`
- decoded ELF +0x131964: `deva-nvaudio`, `devb-mmcsd-tegra3-devlite`
- decoded ELF +0x11f7a8: no NAME record.

Other windows: +0x1834 libnvnordma.so; +0x5834 libnvmnand.so; +0xaca81 mount; +0xb1b8e slogger; +0xb5b8e pipe; +0xbbb8e ksh; +0xf54a0 devg-nvbootprofiler; +0xf94a0 bootprofiler; +0x10569b nvmemctrl; +0x10869b devg-nvsku; +0x10c69b devg-nvos; +0x11069b devg-nvrm; +0x1137a8 devg-nvgpio; +0x1187a8 devg-nvclock; +0x1217a8 i2c-tegra2; +0x1723d3 devc-ser8250-tegra2; +0x1854f3 i2s_init; +0x1884f3 display_init; +0x18b4f3 clock_init.

**Interpretation:** the prior large 'unknown' gaps contain metadata for multiple QNX components. The 27 NAME records are build metadata, not proven 27 independent files: NAME-to-ELF ownership is still proximity-based, and several ELF signatures have inconsistent section tables. Next investigation should report exact NAME byte offsets relative to each ELF and inspect whether the intervening data contain additional ELF signatures or self-contained embedded modules.

## Locate 27 QNX NAME fields in decoded Stage1

Added `tools/fpk1/map_stage1_name_record_coordinates.py` to map every recovered NAME entry (currently 27 on user firmware) to its exact suffix-local decoded position, nearest preceding and subsequent *strict* ELF candidates, distance to each, preceding raw ELF magic within 256 KiB (strict or not), and local zero density. This is a diagnostic to distinguish multiple build records within an ELF-to-ELF interval; proximity is not evidence of separate executable modules or authenticated file catalog entries. Two synthetic regression tests added in `test_map_stage1_name_record_coordinates.py`. On local firmware: `python3 tools/fpk1/map_stage1_name_record_coordinates.py <zip> --json /tmp/fpk1-name-coordinates.json`. For each additional component io-blk.so, fs-qnx6.so, dumper, devb-mmcsd-tegra3-devlite, inspect `record_start`, `offset_from_preceding_elf`, `nearest_preceding_elf_magic`, and `nearest_magic_is_strict`.

## Five additional raw ELF magic candidates, not yet validated

User ran the 27-NAME coordinate mapper. The nearest preceding raw ELF magic for five build records differs from the prior *strict-valid* candidate: `io-blk.so` NAME +0x61c12 → magic +0x2fb06; `fs-qnx6.so` NAME +0x85dd7 → magic +0x7021a; `dumper` NAME +0xaa9e5 → magic +0x90843; `ksh` NAME +0xf3ac4 → magic +0xc0b8e; `devb-mmcsd-tegra3-devlite` NAME +0x1677e7 → magic +0x151f95. None of these five appear among the prior 24 strict-valid ELF candidates. It is not yet known whether they represent legitimate QNX ELFs rejected due to validator assumptions, incomplete/corrupt images, or misleading magic matches. The original association of `ksh` to +0xbbb8e and the four other extra NAME associations must therefore remain tentative.

Added `tools/fpk1/diagnose_stage1_rejected_elf.py`, which reports exact ELF header fields and PHDRs for those five offsets, existing validator result and reason codes; does not weaken strict validation. Run against local archive and resolve header validation before revising the count of recovered ELF objects.

## Five rejected ELF headers explained: ARM exception unwind program segment

User diagnostics for five raw ELF signatures (`io-blk.so` +0x2fb06, `fs-qnx6.so` +0x7021a, `dumper` +0x90843, `ksh` +0xc0b8e, `devb-mmcsd-tegra3-devlite` +0x151f95) showed zero basic header precheck errors; all were rejected exclusively with `unknown_program_type:0x70000001`. Official ARM AAELF32 defines `PT_ARM_EXIDX = 0x70000001` (exception unwind tables), alias `PT_ARM_UNWIND`. Reference: https://github.com/ARM-software/abi-aa/blob/main/aaelf32/aaelf32.rst . Updated `validate_stage1_unseeded_lzf.py` to accept this and `PT_ARM_ARCHEXT = 0x70000000` only for ARM ELF32; did not weaken size or alignment constraints or admit arbitrary processor segment values. Added synthetic tests `test_stage1_arm_program_types.py` for accepted types and rejecting an unknown one. User also reported 30 raw ELF magic occurrences; the adjusted total number of strict-valid ELF and remaining unclassified header(s) must be established by rerunning the firmware validator; do not assert 29 until then.

## Full ARM ELF validation count after PT_ARM_EXIDX correction

User reran `validate_stage1_unseeded_lzf.py` on the original local Q7 Stage1 archive after allowing the standard ARM `PT_ARM_EXIDX` program header. For the `0x1318fc` LZF suffix: **30 raw ELF magic occurrences and 30 strict-valid ELF candidates**. The old count of 24 was a false underestimate caused by the missing ARM program type. This validates ELF headers and program-segment structure, not original imagefs directory paths or full reconstructed file boundaries. The 27 recovered `NAME=` build records must now be re-associated against all 30 valid ELF starts; previous proximity mappings made with 24 ELF are obsolete. In particular, do not assume that `30 - 27 = 3` directly identifies three unnamed files before inspecting distribution of build records.

## Complete 30 ELF to 27 NAME mapping after validator correction

User reran the name-coordinate mapper with the corrected ARM program types. Result: **30 strict-valid ARM ELF candidates** and **27 NAME build records**, distributed one name per ELF except three strict ELF candidates without NAME in their respective ELF windows: +0xbbb8e (between `pipe` and `ksh`), +0xfb4a0 (between `bootprofiler` and `nvmemctrl`), and +0x11f7a8 (between `devg-nvclock` and `i2c-tegra2`). The earlier second-name associations have resolved into distinct ELF candidates: +0x2fb06 `io-blk.so`, +0x7021a `fs-qnx6.so`, +0x90843 `dumper`, +0xc0b8e `ksh`, +0x151f95 `devb-mmcsd-tegra3-devlite`. All names are inferred from proximal QNX build metadata, not verified imagefs paths.

Added `tools/fpk1/inspect_stage1_unnamed_elf.py` to report ELF interpreter, DT_NEEDED, SONAME and selected identifying strings for the three unresolved ELF candidates, without exporting proprietary binary data. Run locally to resolve the last three identities. Note: the investigation of full imagefs directory, original stream framing, and boot sequence is still pending.

## Identification clues for the final three NAME-less ELF candidates

User ran `inspect_stage1_unnamed_elf.py` on original Q7 Stage1:

- **+0xbbb8e**: ET_EXEC, PT_INTERP `/usr/lib/ldqnx.so.2`, DT_NEEDED `libc.so.3`. Notable diagnostic strings: `Invalid APS partition` and `%s: Invalid node "%s" (%s).`. The executable's identity is still unknown. These messages alone are insufficient to assign it an APS-management filename.
- **+0xfb4a0**: ET_EXEC, `/usr/lib/ldqnx.so.2`, no DT_NEEDED recorded. It contains `Usage: sifsloader -a n -i name -m path [-i name -m path] [-v n] [-t]`, `sifsloader: Failed to mount image %s at %s.`, `Successfully mounted image`, `Invalid partition table version`, and decompressor block header/checksum errors. **High-confidence embedded program name: `sifsloader`**, even though no QNX `NAME=` build record was found. Also references `libnvnordma.so` and `libnvmnand.so` as strings; these are not DT_NEEDED dependencies.
- **+0x11f7a8**: ET_EXEC, `/usr/lib/ldqnx.so.2`, DT_NEEDED `libc.so.3`. Strings `/dev/nvsku/rev`, `open(/dev/nvsku/rev) failed`, `/bin/driver/devg-nvrm`, and `execl(/bin/driver/devg-nvrm) failed`. Functional role is strongly suggested as a launcher or initializer for NVIDIA resource manager, but filename remains unknown.

Thus there are 30 validated ELF candidates; 27 QNX build NAME records, plus one highly confidently identified additional executable `sifsloader` by embedded usage text, and two without proven names. Function cannot be equated with verified filename unless corroborated by an imagefs catalog or other metadata. The archive's full imagefs directory, stream framing, and original executable launch order remain unresolved.

## sifsloader-focused format investigation

Added read-only `tools/fpk1/inspect_stage1_sifsloader.py`. The ELF at suffix-local +0xfb4a0 is identifiable as `sifsloader` from embedded usage/errors. The probe records its DT_NEEDED, interpreter, program segments, and all matching embedded strings about SIFS, image mounting, partition tables, block checksums, and compression, with precise ELF-relative coordinates. This is the next evidence-collection step before attempting SIFS header parsing.

Current user-provided evidence **does not yet determine** the SIFS partition-table binary layout, checksum primitive, compression scheme, or whether SIFS images use the same LZF token format seen in the Stage1 suffix. Strings mentioning `libnvnordma.so`/`libnvmnand.so` are clues about interfaces, not DT_NEEDED dependencies. No QEMU boot claim can be made on that evidence alone.

Run `python3 tools/fpk1/inspect_stage1_sifsloader.py <firmware.zip> --json /tmp/fpk1-sifsloader.json` and review `strings`, `segments` and `elf`. Further reverse engineering should target the ELF code paths that reference partition-version, decompressor-block and checksum diagnostics, and cross-check any format proposal against independently observed archive bytes.

## Work-mode verification: SIFS table, Adler-32 and complete Stage2 images

Executed against the local `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip`
(45,883,438 bytes; SHA-256
`bd00b54fd523ad3c07ad14e6c0a76e8d6e3a5a80dfc83dba3b22e0c14d1565a0`).
These results supersede earlier uncertainty about this update's Stage2 framing;
they do not establish the Stage1 startup format or a general SIFS specification.

`inspect_stage1_sifsloader.py --code-evidence` uses optional Capstone to report
selected ARM instruction windows, translated through executable PT_LOAD ranges.
Within the suffix-local loader ELF at +0xfb4a0, the code shows:

- VA `0x102b18`: table version at header +8 must equal 2. Header +0xc is the
  partition count (at most 16), and +0x10 is the following table byte count.
- VA `0x102c38`: each partition has at most four parts. A partition record is
  an eight-byte name plus a u32 part count, followed by that many 32-byte parts.
  VA `0x102de4` advances each part by 0x20; records are **variable length**.
  The previous two-fixed-44-byte-record interpretation omitted a NAND part.
- VA `0x103068` onwards: a compressed block has four LE u32 fields: checksum,
  magic `0x41303200`, compressed length, uncompressed length. Payload starts at
  +0x10. The loader calls VA `0x104c98` with seed 1 over block +4 for
  `compressed_length + 12` bytes, comparing the result against block +0.
- VA `0x104c98`: the checksum routine maintains two sums with modulus 65521
  (`0xfff1`) and combines them as low/high 16-bit halves: Adler-32. VA
  `0x103120` calls the decompressor at `0x104980`, then checks output length.

These are static code observations. Some embedded diagnostic-string pointers do
not resolve to the expected text under a naive ELF VA-to-decoded-byte mapping;
no direct string cross-references or faithful reconstruction of the entire loader
are claimed. The format interpretation is independently checked against real
Stage2 bytes, all block checksums, and actual LZO output.

Coordinate correction: Stage2's `CIFS` prefix begins at **raw ZIP-member +0xba**.
The old probes start at raw +0xc2, eight bytes later. Thus IFSPTTBL is at
CIFS +0x800 (old coordinate +0x7f8); the 32-byte header ends at CIFS +0x820.
The following table has 120 bytes and ends at CIFS +0x898, the NOR part-data
base. Existing probe offsets remain in their older convention; do not mix them.

| Image / part | Storage | Compressed | Offset field | Stored bytes | Logical bytes | Chunk bytes |
| --- | --- | --- | --- | --- | --- | --- |
| STAGE2.1 / 0 | NOR | yes | 0 | 0x93cc87 | 0x174d718 | 0x40000 |
| STAGE2.2 / 0 | NOR | no | 0x93cc90 | 0xcbf400 | 0 (unused) | 0 |
| STAGE2.2 / 1 | NAND | yes | 0x200200 | 0x88c0f4 | 0xef6a34 | 0x40000 |

NOR offsets are relative to CIFS +0x898, **not** to CIFS +0. In particular the
uncompressed STAGE2.2 part starts at CIFS +0x93d528, directly on `imagefs\x04`.
The NAND update has `ESO_BIN\0` at raw +0xba; its first compressed block starts
at payload +0x200 (raw +0x2ba). Mapping flash offset 0x200200 to that position
implies a flash base of 0x200000 for this member. This mapping is specific to the
observed update; it is corroborated by every block checksum and output size.

Added `verify_sifs_partitions.py`, invoked through the existing loader inspector:

```sh
# Standard-library-only table and checksum checks:
python3 tools/fpk1/inspect_stage1_sifsloader.py <firmware.zip> --verify-stage2
# In an environment with capstone and lzokay installed:
python3 tools/fpk1/inspect_stage1_sifsloader.py <firmware.zip> \
  --code-evidence --verify-stage2 --decompress --json /tmp/fpk1-sifs-verified.json
python3 -m unittest discover -s tools/fpk1 -p 'test_*.py' -v
python3 tools/fpk1/check_machine.py --qemu ./build-fpk1/qemu-system-arm
```

Actual results: **72/72 Adler-32 checks pass**, and all **37 NOR + 35 NAND**
compressed blocks decode successfully with `lzokay`. This establishes compatibility
with that LZO decoder, without claiming exact compressor provenance. Each block's
output length and both complete imagefs header sizes match. STAGE2.2 is formed by
concatenating its uncompressed NOR part and decoded NAND part, in table order.

| Complete in-memory image | Size | SHA-256 |
| --- | --- | --- |
| STAGE2.1 | 24,434,456 (0x174d718) | `cc0d8fbfea80e0903036d8336c217985a72e3cdd2466bb2281e6a02e4b67da85` |
| STAGE2.2 | 29,056,564 (0x1bb5e34) | `e9eab3346af5a92775e402d71572d30a0d317cdaf5a08e85b89727fd85095f00` |

Both checksum-only and full-decompression modes were run. All **30** firmware-free
unit tests pass, including new variable-record, truncation, corrupted checksum,
block-header, partial-final-chunk and logical-size checks. The existing QEMU
smoke test also passes using the already built `build-fpk1/qemu-system-arm`:
machine listing, required-address diagnostics, invalid entry rejection and a
synthetic ARM loop. This is an initialization check, **not a QNX firmware boot**;
no new QEMU compilation was performed in this run. No proprietary binaries are
written or included in the commit; reconstructed images exist only in memory.

Next: inspect the verified Stage2 imagefs directories in memory for startup
scripts and dependency paths, then connect these findings to the unresolved
Stage1 startup and hardware handoff. Stage1 LZF suffix decoding and Stage2 LZO
blocks are separate observations and must not be equated.

## Verified Stage2 catalogs and the Stage3 script handoff

Added `tools/fpk1/inspect_stage2_catalogs.py` for the fully reconstructed images.
It uses the SIFS verifier's optional in-memory inspection callback, so no image
or extracted file needs to be written. It validates the imagefs additive u32
checksum (zero modulo 2^32), bounded catalog terminator, record extents, canonical
paths, regular-file extents and symbolic-link string lengths before reporting
metadata. The firmware-independent tests exercise checksum corruption, malformed
records, unsafe/duplicate paths, out-of-bounds files, missing terminators and
bad symlink lengths.

Executed on the same Q7 0378 archive identified in the preceding section:

| Image | All records | Regular files | Directories | Symlinks | ELF files |
| --- | --- | --- | --- | --- | --- |
| STAGE2.1 | 178 | 157 | 3 | 18 | 76 (62 ET_DYN, 14 ET_EXEC) |
| STAGE2.2 | 345 | 344 | 1 | 0 | 2 (ET_EXEC) |

Both additive checksums equal zero. All 501 regular-file spans are present in
memory and inside the reconstructed image data. Each of the 78 ELF files passes
the existing strict ARM program-header validation **within its own catalog file
extent**; metadata cannot bleed into the following file. All 16 ET_EXEC objects
request `/usr/lib/ldqnx.so.2`. STAGE2.2's executables are `bin/mostcoreapp` and
`bin/imgdec`; most of its other files are resources. The previous report that only
7 of its 344 files fit applied to the incomplete stored-byte view, not to these
verified reconstructed images.

The root directory is a valid empty-name record. Symlinks require a different
layout from directories: a u16 target offset (relative to the path at +28) at
record +24, and a u16 target size at +26. On all 18 observed links, the offset
equals the name length including NUL, and target size excludes its NUL. Treating all nonregular
names as starting at +24 produces control characters and false paths.

Catalog-confirmed links include:

- `stage3` → `/mnt/stage3`
- `bin/sh` → `/bin/ksh`
- `etc/scripts` → `/stage3/etc/scripts`
- `etc/usblauncher` → `/stage3/etc/usblauncher`
- `lib/libsocket.so` → `libsocket.so.3` (relative target)
- `lib/libecpp-ne.so` → `libecpp-ne.so.4`
- `lib/libz.so` → `libz.so.2`

Three allowlisted Stage2.1 shell scripts were read from validated file extents:

| Path | Bytes | Observed behavior |
| --- | --- | --- |
| `bin/start_stage3.sh` | 222 | Checks `/tmp/stage3_started`, returns if present, otherwise creates it, waits for `/stage3/bin/stage3.sh`, then invokes that script with `/bin/ksh`. |
| `bin/gtf2_error_fallback.sh` | 172 | Sleeps 30 seconds; exits if the marker exists; otherwise invokes `/bin/start_stage3.sh`. This is a fallback path if the script itself is launched. |
| `bin/copy_tmp_core_dumps.sh` | 97 | Waits for `/mnt/temp_fpk/dumps/`, then copies `/tmp/*.core` there. |

The marker check and creation are separate shell commands, not an atomic lock.
The script contents do not establish who first invokes `start_stage3.sh`, whether
the fallback is armed, or when `/mnt/stage3` is actually mounted.

The optional `--with-stage3` cross-check uses the existing read-only QNX6 volume
reader on `stage3.img`. It confirms `/bin/stage3.sh` (359 bytes) and
`/bin/startup-common.sh` (953 bytes). Static script handoff:

1. Stage2 `start_stage3.sh` waits for and invokes `/stage3/bin/stage3.sh`.
2. Stage3 `stage3.sh` invokes `/stage3/bin/startup-common.sh`, then names services
   including `devg-nvtmon`, `diagnosis`, `fds`, core-dump handling and `grengme`.
3. `startup-common.sh` sets `LIBPATH` to `/lib:/stage3/lib` and `PATH` to
   `/bin:/stage3/bin`. Its commands start USB initialization, `io-pkt-v4-hc`,
   `inetd`, a RAM disk/PPS, USB launchers, INIC support and other services.
   Several waits require real device nodes, e.g. `/dev/nvgpio/vcm_usb_on1` and
   `/dev/io-usb/io-usb-most`; their presence under QEMU is not established.

This describes script contents and call relationships, **not successful runtime
execution**. It exposes additional device/service dependencies beyond decompression.

ELF DT_NEEDED across Stage2 references **37 distinct library names**; **31** have
at least one regular-file or symlink basename match in these catalogs. Six do
not: `libc.so.3`, `libm.so.2`, `libnvclockapi.so`, `libnvos.so`, `libnvrm.so`,
`libnvrm_graphics.so`. The exact `/lib/<name>` paths were also absent from the
inspected Stage3 volume, as were `/usr/lib/ldqnx.so.2` and `/bin/ksh`. This does
not exclude other paths, installed content or providers in Stage1. Basename
presence is not runtime linker resolution; mount order and inherited search
paths must still be established. Stage1's partial suffix already contains a
`ksh` build record, but its original imagefs path is still unverified.

Reproduce in an environment with `lzokay` installed:

```sh
python3 tools/fpk1/inspect_stage2_catalogs.py <firmware.zip> \
  --with-stage3 --json /tmp/fpk1-stage2-catalogs.json
python3 -m unittest discover -s tools/fpk1 -p 'test_*.py' -v
```

The JSON contains catalog metadata, bounded ELF dependency metadata, five
allowlisted script texts with SHA-256 values, and exact Stage3 path-check results.
No credential-file contents, executable payloads or reconstructed filesystem
images are exported. Local validation passes: all **38** tests, real-archive
catalog/ELF/script inspection, all **72** underlying SIFS block checksums and LZO
length checks, plus the pre-existing checksum-only inspector mode after the
callback extension. No QEMU implementation changed or new boot attempt was made.

Next priority is the earlier boot chain: recover a complete Stage1 imagefs and
its startup script/core-library paths, identify the caller of the Stage3 scripts
and the mounts it prepares, and establish the CPU/entry/hardware handoff before
attempting QNX execution.

## Complete Stage1 ZV/LZF reconstruction and startup script

**This supersedes the raw startup-header contradictions and unframed suffix
inventories above.** The primary Stage1 payload is a length-delimited stream of
standard ZV/LZF frames. The framing matches the primary
[liblzf command-line source](https://github.com/nemequ/liblzf/blob/master/lzf.c):
compressed frames have a seven-byte header with two big-endian u16 sizes;
uncompressed frames have a five-byte header. Decode history resets per frame.
Treating intervening frame headers as LZF tokens caused corrupted decoded file
contents, shifted strings and incorrect dynamic dependencies in prior probes.
Structurally valid ELF headers alone did not establish faithful file contents.

`tools/fpk1/inspect_stage1_framed.py` uses the existing bounded LZF token decoder
separately for each frame. The observed primary-image envelope specifies:

| Field / result | Value |
| --- | --- |
| Coordinate origin | raw ZIP member +0xc2 |
| Frame stream start | +0x7f8 (raw member +0x8ba) |
| Stored length, u32 at +0 | 0x1f656c, including the four-byte CRC32 trailer |
| Frame stream end | +0x1f6d60 |
| Trailer / calculated decoded CRC32 | 0x53a13ff7, equal |
| Frames | 58 compressed, no uncompressed frames in this update |
| Decoded bytes | 3,788,832 (0x39d020) |
| Decoded SHA-256 | `adec09b69c71719a6e9d5db944e1467c335e3054e1c4aae5c02c7a93b0edd503` |

The first 57 frames each produce 65,535 bytes; the last produces 53,337.
The stored length reaches exactly through the CRC32 trailer. Later envelope
padding and metadata are excluded; their remaining checksum semantics have not
been established. No arbitrary suffix endpoint is used.

After decompression the ARM stub occupies decoded +0..+7, followed by a coherent
QNX startup header at +8. Corrected fields:

| Startup header field | Value |
| --- | --- |
| version / header_size / machine | 1 / 0x100 / ARM (40) |
| preboot_size | 8 |
| startup_vaddr | 0x80a06b98 |
| image_paddr / ram_paddr | 0x80a00808 / 0x80a00808 |
| startup_size | 0x1a108 |
| stored_size / ram_size | 0x39d018 / 0x39d018 |
| imagefs_size | 0x382f10 |
| internal QNX compression bits | 0 (the outer ZV stream has already been decoded) |

The startup checksum from the signature through the startup trailer sums to
zero modulo 2^32. Its declared end is decoded +0x1a110, where the complete
imagefs begins. The imagefs checksum independently sums to zero. Its SHA-256 is
`843c1a00f9e77f3125f33f0e48494f6730f1ec9227697fd2966a4f1b8c205fa3`.
The header-consistent load address for the decoded stub is 0x80a00800; the entry
0x80a06b98 maps to decoded +0x6398, now containing coherent ARM startup code.
This is a validated decoded mapping, not proof of the installed bootloader's
real CPU/handoff state.

The complete Stage1 catalog contains **54 records: 47 regular files, six
symlinks and one root directory**. Forty-three regular files are strict-valid
ELFs inside their actual catalog-owned bounds. The imagefs bootstrap inode
selects `proc/boot/procnto-smp-instr`; the script inode selects the 3,808-byte
`proc/boot/startup.script`. These identities are catalog-backed, unlike the
previous proximity guesses. The previously unresolved objects are now proven:

- `bin/waitfor_eso` (14,832 bytes), previously the +0xbbb8e suffix candidate.
- `bin/sifsloader` (39,000 bytes), previously +0xfb4a0.
- `bin/driver/devg-pre` (7,024 bytes), previously +0x11f7a8.

The faithful `sifsloader` ELF has **22 dynamic entries** and DT_NEEDED
`libnvnordma.so`, `libnvmnand.so`, `libc.so.3`. Prior claims of no DT_NEEDED and
only string-based NOR/NAND library evidence were artifacts of unframed decoding.
`inspect_stage1_sifsloader.py` now defaults to this verified catalog-owned file;
`--legacy-suffix` retains the old probe with an explicit corruption warning.

All six Stage2 library names previously lacking coverage are actual Stage1
regular files under `lib/`. Across the combined Stage1 and Stage2 catalogs,
**all 46 distinct DT_NEEDED names** have regular-file or symlink basename
coverage. This does not prove mount order or runtime linker success.

The startup script is binary, not a shell script. A bounded parser follows the
record shapes in QNX's published
[`sys/image.h`](https://github.com/vocho/openqnx/blob/master/trunk/services/system/public/sys/image.h),
checking record boundaries, argument/environment counts, NUL termination and
padding. It yields **47 records: 36 external commands, nine wait operations,
one console reopen and one process-manager symlink**. The header's script inode
selects this file directly. Observed order and parameters include:

1. Create the loader link from `../../lib/libc.so.3` to `/usr/lib/ldqnx.so.2`.
2. Start logging/profiling and wait for their device nodes.
3. Start `sifsloader` in the background with NOR offset **30801920 (0x1d60000)**,
   loading `STAGE2.1` and `STAGE2.2`, both mounted at `/`.
4. Start the eMMC driver with controller `0x78000600`, IRQ 63, eight-bit bus,
   and `skipinit` among its options. Start serial at `0x70006000`, IRQ 68.
5. Run NVIDIA memory/SKU/clock/GPIO/OS setup, I2S, I2C, audio and display setup.
6. Launch `ksh /bin/mount_nand.sh` in the background. That script waits for
   `/dev/emmc0` and invokes `mount -t qnx6 -a`.
7. Wait for `/bin/gss_ipc`, then start Stage2 applications including `gss_ipc`,
   `broker`, `kdgui_2dmgr`, `gtf2`, capture, audio, MOST and tracing components.
8. Arm `ksh /bin/gtf2_error_fallback.sh` in the background, then invoke `tinit`.

Thus the earlier uncertainty about whether the 30-second Stage3 fallback is
armed is resolved: the boot script launches it. Its successful execution still
depends on the preceding boot steps. The primary non-fallback caller of
`start_stage3.sh` remains unresolved.

`etc/fstab` maps eMMC QNX6 partitions explicitly:

| Device | Mount point | Mode |
| --- | --- | --- |
| `/dev/emmc0t177.3` | `/mnt/persist_swdl` | rw |
| `/dev/emmc0t177.4` | `/mnt/temp_fpk` | rw |
| `/dev/emmc0t177.5` | `/mnt/persist_fpk` | rw |
| `/dev/emmc0t177.6` | `/mnt/stage3` | ro |
| `/dev/emmc0t177.7` | `/mnt/app` | ro |

These link the previously verified Stage2 `stage3` symlink and Stage3 shell
scripts to the earlier storage/mount sequence. The eMMC `skipinit` option is a
concrete inherited-state requirement to investigate, not proof that the QEMU
controller already satisfies it.

Source-layout correction: imagefs byte +7 is flags (0x04 means inode flags are
valid), not a filesystem "version 4". The first symlink u16 is a target offset
relative to its path field; it happened to equal NUL-terminated name length in
every observed link. The catalog parser now names it as an offset. The strict
`imagefs\x04` profile remains intentional for the three inspected images.

Reproduce the primary decode and combined dependency inventory:

```sh
# Primary Stage1 uses only the Python standard library:
python3 tools/fpk1/inspect_stage1_framed.py <firmware.zip> --json /tmp/fpk1-stage1.json
# Combined Stage1/Stage2 inventory requires lzokay:
python3 tools/fpk1/inspect_stage1_framed.py <firmware.zip> \
  --with-stage2 --json /tmp/fpk1-stage1-stage2.json
python3 tools/fpk1/inspect_stage1_sifsloader.py <firmware.zip> \
  --code-evidence --verify-stage2 --decompress --json /tmp/fpk1-sifsloader-framed.json
python3 -m unittest discover -s tools/fpk1 -p 'test_*.py' -v
```

All **46** firmware-free tests pass. New cases cover independent frame history,
raw/compressed framing, truncation/output limits, declared lengths and CRC32,
startup checksum/address invariants, and binary-script commands/argument counts.
The real archive passes complete Stage1 and combined Stage1/Stage2 inspection.
Neither the decoded image nor full script contents are committed.

### Bounded execution of decoded startup in the diagnostic machine

Added `probe_stage1_startup.py` to run only the verified decoded image in the
existing local QEMU build. It creates a private temporary boot image, starts
paused, queries the actual AVP CPU index, resumes for at most the requested
host duration (default 200 ms), stops it and captures registers/first exception.
Trace growth is bounded by polling; only a bounded prefix is read. No flash or
disks are attached; temporary boot image and trace are deleted on exit.

Both experiments used load/initial PC **0x80a00800**, 512 MiB RAM, existing
`build-fpk1/qemu-system-arm` and no QEMU source changes or new build:

| Experiment | Observed startup trace | First exception |
| --- | --- | --- |
| Existing diagnostic CPU state | Stub → 0x80a06b98; 643 translated startup block starts, last 0x80a013ac | Data Abort, DFSR 0x1, DFAR 0x3, CPU 5; followed by undefined-instruction exceptions |
| Override `reset-cbar=0x50040000` | Progresses further; 699 startup block starts, last 0x80a0cc00 | Data Abort, DFSR 0x801, DFAR 0xff7, CPU 5; followed by undefined-instruction exceptions |

The baseline final block dereferences a startup-held pointer then reads pointer
+4; this is consistent with an invalid pointer leading to DFAR 0x3. A CBAR
override changes progress and failure location, but is **not a complete fix**.
The diagnostic machine runs its AVP as a Cortex-A9 surrogate; the real CPU
handoff is still unproven. Neither run demonstrates `procnto` or service startup.

```sh
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --json /tmp/fpk1-startup-baseline.json
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --cbar 0x50040000 \
  --json /tmp/fpk1-startup-cbar.json
```

Next: trace the initial startup memory mappings and inherited CPU/MPCore state,
especially the first invalid pointer and the later DFAR 0xff7 access. Only then
change the diagnostic CPU/handoff configuration, with measured before/after
behavior. Recovery Stage1 and outer-envelope checksum fields remain separate
unresolved profiles.

## CPU and memory handoff: procnto entry reached

The earlier two Data Aborts are now localized to individual instructions.
`probe_stage1_startup.py --trace-faults` requests one instruction per TCG block
and records CPU state immediately before the first fault in the two known
startup regions. No firmware instructions are changed.

| Configuration | Exact instruction | Relevant state | Result |
| --- | --- | --- | --- |
| Original AVP profile | 0x80a013b8: load from r3 + 4 | r3 = 0xffffffff; reset CBAR = 0 | Data Abort at 0x3 |
| AVP with CBAR 0x50040000 | 0x80a0cc64: store through r5 + (r2 << 2) | r5 = 0xffffffff; r2 = 0x3fe | Data Abort at 0xff7 |

For the first fault, the startup global at 0x80a18f98 contains 0xffffffff.
With CBAR 0x50040000 that same global contains 0x50040000 and the fault is
passed. The four G-cluster CPUs already receive this CBAR in `tegra30.c`;
the diagnostic AVP surrogate does not. This accounts for the original profile's
incompatible MPCore state without changing the shared SoC implementation.

The second fault occurs while constructing MMU tables. The two allocations
called from 0x80a07d90 and 0x80a07da0 return 0xffffffff; their results are stored
at 0x80a1a7ec and 0x80a1a794. The later table store wraps to 0xff7. An earlier
trace of the RAM-discovery path reaches 0x80a03544 with r0 = 0x80000000 and
r1 = 0, after an unrecognized/empty board-information path chooses zero size.
This is a failed RAM-discovery/allocation path, not a missing 512 MiB QEMU RAM
mapping: the machine already maps that memory.

### Synthetic ATAG memory description

Startup at 0x80a00dfc explicitly maps data at **0x80000100**, searches for
ATAG_CMDLINE (0x54410009), and extracts `mem=` using a space delimiter. Its
memory-option buffer is at 0x80a19f24. Supplying **`mem=512M@0x80000000 `**
including the trailing space lets the existing BSP discover the mapped RAM.
The same text without a trailing space leaves that buffer empty and reproduces
the 0xff7 fault. The probe deliberately preserves an explicit `--atag-cmdline`
verbatim so this negative control remains reproducible.

`--memory-handoff` creates synthetic ATAG_CORE, ATAG_MEM and ATAG_CMDLINE
records, followed by the zero terminator, and loads them at 0x80000100 with
QEMU's generic loader. Their wire format follows the existing
`hw/arm/boot.c:set_kernel_args` implementation. ATAG_MEM declares the same
512 MiB at 0x80000000 as the emulated RAM; it is not sufficient by itself for
the observed BSP path. This supplies boot data expected by the firmware,
without patching the decoded image or guessing a project/SKU identity.

With the valid memory option, the observed L1/table descriptor at 0x80a1a7ec
becomes 0x8000c06a and the table pointer at 0x80a1a794 becomes 0x8001c000.
The original failed allocations and 0xff7 access disappear.

### Execute on a G-cluster CPU

Keeping the AVP as the executing processor after supplying CBAR and memory
reaches the kernel but terminates QEMU with the explicit diagnostic
`a9gtimer: num-cpu 4 but this cpu is 5!`. The modeled MPCore global timer has
four CPU banks and validates `current_cpu->cpu_index`; AVP index 5 is outside
that range (`hw/timer/a9gtimer.c`).

The new **opt-in** `--boot-cpu cpu0` experiment instead uses existing QEMU
interfaces: while paused, set CPU0's `start-powered-off` property false and
AVP's true, reset, and let a generic loader set CPU0's PC to the validated stub.
`hw/core/cpu-system.c` explicitly permits changing this property after realize.
The FPK1 machine and shared Tegra30 sources remain unchanged. CPU0 already has
CBAR 0x50040000 and the GIC/timer wiring appropriate to the G cluster.
This bypasses the unmodeled real bootloader handoff; it does not establish how
installed FPK1 hardware brings up its main CPU.

### Measured result and limits

The combined **CPU0 + memory ATAG + single-thread TCG** profile reaches
**`proc/boot/procnto-smp-instr`'s catalog-owned ELF entry 0xfe054a58**. That exact
address appears in the instruction trace. In two repeated 2,000 ms experiments:

- The first recorded exception is a normal QNX SVC on CPU0, not Data Abort.
- No Data Abort, Prefetch Abort or Undefined Instruction appears in the captured
  trace. Both runs stop at the requested duration and exit by controlled QMP quit.
- CPU0 and CPU1 are sampled at 0xfe0762f4, inside a PT_LOAD range of the verified
  kernel ELF. CPUs 2/3 are at 0xfc411e30; this address is outside those ELF ranges
  and is not labeled as proven kernel execution by the tool.
- The console capture is empty. Startup-script execution, processes, resource
  managers, storage mounts and the display are **not yet demonstrated**.

An exploratory CPU0 run using the build's default multithreaded TCG terminated
with host SIGILL; no cause or fix is assigned to that separate observation.
The reproduced stable profile explicitly uses `--tcg-thread single`. The
AVP/timer mismatch is also captured as a host exit, not misreported as a
successful guest run. The probe now handles exited QEMU sessions and records
stderr through a temporary file to avoid pipe backpressure from crash dumps.

The tool reports actual reset CBAR, all CPU snapshots, kernel-entry trace
presence, physical startup globals, the first fault's preceding register state,
console text and QEMU exit status. SVC is excluded from `first_fault` because it
is an ordinary kernel-entry mechanism. A zero QEMU exit status here means the
probe quit the emulator cleanly, not that the guest completed boot.

Reproduce the controlled comparisons against the existing local build:

```sh
# Exact first failing instruction:
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --trace-faults \
  --json /tmp/fpk1-fault-baseline.json
# Exact failed MMU-table store:
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --trace-faults --cbar 0x50040000 \
  --json /tmp/fpk1-fault-cbar.json
# Negative control: missing command-line delimiter, still faults at 0xff7:
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --boot-cpu cpu0 \
  --atag-cmdline mem=512M@0x80000000 --tcg-thread single \
  --json /tmp/fpk1-no-delimiter.json
# Verified kernel-entry experiment:
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --boot-cpu cpu0 --memory-handoff \
  --tcg-thread single --run-ms 2000 --json /tmp/fpk1-kernel-handoff.json
```

All **51** firmware-independent tests pass. Five new tests cover ATAG wire
lengths, RAM declaration, exact delimiter preservation, invalid handoff inputs,
register selection before the first fault and distinguishing SVC from faults.
All experiments use the same CRC-verified decoded Stage1 and existing QEMU
binary; there is no rebuild, firmware modification, attached disk/flash, or
shared-machine change. Private temporary images/tags/traces are removed; only
bounded diagnostic metadata is reported.

Next: inspect kernel initialization/secondary-CPU state and establish whether
startup-script commands run. Add process/console evidence before claiming a
usable QNX system, then connect the known SIFS/eMMC dependencies to real backing
images and verify the required device behavior.

## ARM64 host SIGILL removed; startup.script programs execute

The apparent two-CPU stop from the previous experiment was an observation of
an early SMP rendezvous, not proof that the remaining CPUs could never enter
QNX. At 0xfe0762f4 code compares the word at 0xfe0b5888 against the configured
CPU count at 0xfe0b5880 (4, initialized from syspage header +6). CPUs 2/3 at
0xfc411e30 poll the syspage SMP mailbox at 0xfc41014c. Virtual-memory inspection
on all four G CPUs translates that mailbox to the same physical 0x8002414c.
The callout consumes its entry with LDREX/STREX; 0xfe08ddf0 is the kernel's
secondary entry. These are runtime words/instructions, not recovered symbols.
Later runs pass this rendezvous; the sampled counter also changes afterwards.

### A separate host instruction-encoding defect

macOS crash reports for the failing local ARM64 build locate SIGILL in TCG's
translation buffer, called by `cpu_tb_exec`, not a guest Undefined Instruction
exception. The faulting native word is **0x1ad506d4**. The register min/max
constants in `tcg/aarch64/tcg-target.c.inc` put the operation bits in the wrong
positions. The local Clang assembler independently produces these words for
`w0,w1,w2` operands:

| Instruction | Assembled word | Correct base word |
| --- | --- | --- |
| smax | 0x1ac26020 | 0x1ac06000 |
| umax | 0x1ac26420 | 0x1ac06400 |
| smin | 0x1ac26820 | 0x1ac06800 |
| umin | 0x1ac26c20 | 0x1ac06c00 |

The host reports `hw.optional.arm.FEAT_CSSC=1`, so TCG selects these instructions.
Only the four base constants change; immediate forms and feature detection are
unchanged. This is a local research-fork fix, not an upstream contribution.
Rebuilding the same binary removes the reproduced SIGILL.

`check_tcg_shifts.py` supplies a firmware-free ARM guest exercising 48 register
LSL/LSR/ASR cases, both signs and counts 0, 1, 31, 32, 40, 255, 256, 257.
A branch before each shift prevents constant folding across the setup and the
shift. It compares all stored results and requires a completion marker. The
original encoding build terminates before completing the test (QMP pipe closes);
the corrected build passes all 48 cases on this CSSC host. This runtime check
exercises UMIN lowering; the assembler comparison validates all four constants.
On other host architectures the same guest checks their shift semantics.

### Positive execution evidence for four startup commands

With the corrected build, synthetic CPU0/ATAG handoff and
`--tcg-thread single --icount-shift 0`, a bounded 2,000 ms host-time run captures
entry blocks for the following verified Stage1 files:

| Catalog file | Linked ELF entry | Exact prefix matched |
| --- | --- | --- |
| bin/slogger | 0x00100f90 | 32 bytes |
| bin/profiling/devg-nvbootprofiler | 0x00100d10 | 32 bytes |
| bin/sifsloader | 0x00101e70 | 32 bytes |
| bin/driver/devb-mmcsd-tegra3-devlite | 0x001023c8 | 32 bytes |

Each match requires an `exec` record for the entry and the actual instruction
bytes from `in_asm`, compared against the corresponding PT_LOAD file bytes. Each is unique at that
entry within the complete Stage1 catalog. An address in the common 0x00100000
program range alone is insufficient, since different processes reuse virtual
addresses. The probe reports ambiguous matches explicitly and gives no match
when a QEMU disassembler omits the raw `OBJD-T` byte format.

These files occur in the decoded startup.script in the same launch sequence.
This demonstrates execution of its early commands, including **sifsloader**;
it does not demonstrate their successful initialization, daemon readiness or
SIFS mounts. No flash or disk has been attached in this experiment. The UART
capture remains empty; there is no entry match for the serial driver in this
bounded observation.

The captured trace also contains a Data Abort from **EL0 to EL1**, first reported
on CPU0 with DFAR 0x000fdcf0 and DFSR 0x807. This differs from the earlier
EL1 startup faults. It must not be classified as a fatal process crash merely
from the exception: demand paging and recovery have not been distinguished.
The run continues, stops at its requested duration, and QEMU exits by QMP quit.

### Reproduction and remaining work

```sh
make -C build-fpk1 -j6 qemu-system-arm
python3 tools/fpk1/check_tcg_shifts.py --qemu ./build-fpk1/qemu-system-arm
python3 tools/fpk1/probe_stage1_startup.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --boot-cpu cpu0 --memory-handoff \
  --tcg-thread single --icount-shift 0 --kernel-state \
  --trace-limit-kib 8192 --run-ms 2000 --json /tmp/fpk1-program-entries.json
```

Kernel-state mode logs `in_asm,int,exec` for the kernel entry and low program
addresses, omitting startup/SMP spin loops from instruction/execution logging.
The default 256 KiB trace bound can stop this profile before the program entries;
use the explicit larger bound for this comparison. The maximum trace bound is
8 MiB (with a bounded read allowance and an explicit truncation flag); run time
is limited to 10 seconds. These limits measure host time/trace size, not guest
boot completion. `icount` changes guest time advancement and scheduling, and is
reported in the metadata. Kernel-state sampling is guarded by the exact decoded
Stage1 SHA256; other firmware cannot silently reuse these addresses. Timer/GIC
reads are debug views of CPU0's bank and do not imply other CPUs have identical
banked state.

Validation: **57** firmware-independent unit tests, the diagnostic machine smoke
check, and all 48 guest shift cases pass. New tests reject invalid clock/trace
settings, wrong firmware profiles, wrong entry bytes/addresses, short evidence, missing execution records
and ambiguous stubs. Firmware bytes and temporary images/traces are not added
to Git. The user's pre-existing `.gitignore` changes remain separate.

Next: trace sifsloader's actual mapping/access outcome and the eMMC driver's
initialization/wait path; establish service readiness and supply validated
storage backing before claiming Stage2 mounts or a usable console.

## Bootloader command line, eMMC and boot to Stage3

The previous NOR/storage experiment (`--stage2-nor --storage-trace`) shows
sifsloader reading NOR and decoding STAGE2.1, but the UART then only printed
`i2s_init: Invalid Project 0` and `display_init: Invalid Project -1`. Two
missing inputs explain this; supplying both lets the original startup.script
run through Stage2 into the Stage3 fallback without patching any firmware.

### Board identity is passed by Quickboot on the command line

`devg-nvsku` publishes `/dev/nvsku/{project,sku,rev,...}` from syspage asinfo
entries (`nvsku`, `nvprod`, `serial_info`, `is_e1888`). The Stage1 startup
creates those entries from the ATAG command line: at 0x80a00dfc it parses
`tegraprof=`, `nvsku=`, `lp=`, `SkuVer=`, `ProdInfo=`, `ProdVer=`,
`is_e1888=`, `mem=` and `emmc_skipinit=` (buffer 0x80a19f00), and also looks
for ATAG types 0x5441000f and 0x54410006. Fields are split on `-` and parsed
as decimal (0x80a031d0): field 1 is the project, field 2 the SKU, field 3 the
revision. Startup accepts projects **0xf19c (61852)** and **0xf1a2 (61858)**;
61852 matches the `embedded-qnx-p1852` BSP path. The Quickboot payload
(`qb_primary.img`, identical in `qb_recovery.img`) contains the producer
formats verbatim: `nvsku=%03d-%05d-%04d-%03d SkuVer=%c%c`,
`ProdInfo=%03d-%05d-%04d-%03d ProdVer=%c%c`, `is_e1888=%d `, `mem=%uM@%uM `
and `emmc_skipinit=1 `, i.e. NVIDIA `699-<project>-<sku>-<rev>` part numbers.

`display_init` accepts SKU 1, 2, 5 and 8 for both projects; `i2s_init` only
auto-configures SKU2 or SKU5. `devg-nvgpio` has two GPIO tables: one with
`start_mode_to_gss`, `hsk_to_kss`, `most_*` and `vcm_usb_on1` (which Stage3's
startup-common.sh waits for), another with head-unit lines (`nad_*`, `ipod_*`,
SD). Four 120 s runs with identical other inputs:

| nvsku project-SKU | Result |
| --- | --- |
| 61852-2, 61858-2 | `display_init: Unable to set modes`, LVDS serializer I2C errors, `gss_ipc: Unable to determine KSS mode!` |
| 61852-5, 61858-5 | `display_init: successfully set modes`, `KSS Application mode`, Stage2 apps start |

SKU5 is therefore used. Project 61852 vs 61858 produced no observable
difference; 61852 is chosen from the BSP path, not proven. Revision 200,
`SkuVer=A0` and `is_e1888=0` are placeholders. `run_stage1_console.py
--board-info` supplies this synthetic line (`BOARD_CMDLINE`).

### STAGE2.2 and the mounts need an eMMC

With SKU5, sifsloader prints `NandDma: Device '/dev/emmc0' appeared`, then
`Failed to load image STAGE2.2`: as established in the SIFS table, STAGE2.2
part 1 lives on raw eMMC at byte 0x200200, i.e. `stage2_nand.img`'s
`ESO_BIN` payload at 0x200000. `mount -t qnx6 -a` (mount_nand.sh) needs the
fstab partitions `emmc0t177.3..7`.

`hw/arm/fpk1.c` now attaches an optional `TYPE_EMMC` card to SDMMC4
(0x78000600) when `-drive if=sd,index=0,...` is given, like `mhi2-harman`;
without the drive the machine is unchanged. `create_fpk1_emmc.py` assembles a
sparse 1 GiB image from the archive: `stage2_nand` payload at 0x200000, MBR
with three type-177 primaries (`t177`, `.1`, `.2`, left unformatted) and an
extended chain of five type-177 logicals: `.3`–`.5` empty 32 MiB QNX6
volumes (with `dumps/`), `.6` the zlib-expanded `stage3.img`, `.7` `app.img`.
Partition placement and t177.0..2 contents are synthetic.

fs-qnx6 reports errno 302 ("Corrupted file system detected") for a QNX6 volume
smaller than its partition. Measured on four variants: volumes sized exactly to
the partition mount with or without spare inodes and a `dumps/` directory,
while the same volume 2.8 MiB smaller fails. Growing a volume via
`qnx6_image.build(partition_blocks=...)` leaves blocks beyond the bitmap and
produced `No space left on device`; the tool instead grows free data blocks
until the image size matches.

### Measured boot

```sh
python3 tools/fpk1/create_fpk1_emmc.py <firmware.zip> /tmp/fpk1-emmc.img
python3 tools/fpk1/run_stage1_console.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --icount-shift 0 --board-info \
  --emmc /tmp/fpk1-emmc.img --seconds 240 --json /tmp/fpk1-console.json
```

The run uses the same CPU0/ATAG handoff and synthetic Stage2 NOR, without
instruction tracing (`-d unimp,guest_errors` only), and attaches the eMMC with
`snapshot=on`. Without `-icount shift=0` the UART stayed empty for 60 s, so
the clock setting matters. Observed console milestones (host seconds):

| t | Evidence |
| --- | --- |
| 1.0 | `Generic SDHCI ... MMC:170 QEMU!!` (eMMC enumerated) |
| 1.8 | `display_init: successfully set modes` |
| 2.8–5.8 | `gss_ipc`: KSS application mode, startup finished |
| 8.0 | `login:` prompt on the serial console |
| 10.8 | gtf2/EAL `Variant: fpk1`; `display_create_window` fails |
| 62.5 | AliveManager: `hmi`, `kdgui_2dmgr`, `diagnosis`, `swdlclient` failed to start |
| 65.1 | `--- Error with gtf2 detected. Starting stage 3... ---` |
| 65–71 | Stage3: USB init, USB Ethernet with TCP/IP, INIC driver, `CHALLENGE: Running on port 22111` |

No `Corrupted file system`, mount or STAGE2.2 load error appears; audio
samples from STAGE2.2 are found. The Stage3 handoff happens through the
30 s `gtf2_error_fallback.sh` path because gtf2 never becomes ready.

### Remaining blockers

1. **Graphics**: `kdInitializeNV`/`display_create_window` fail
   (`KD_EOPNOTSUPP`, then `KD_ENOMEM`); `kdgui_2dmgr_ready` never appears.
   The NVIDIA display/host1x/2D path is not emulated. This is the next
   priority, as gtf2 is the cluster HMI.
2. I2C peripherals: TLV320DAC3100 DAC (`audio_player` requests reboot), MOST
   INIC over I2C (`NSR_E_NO_COMM` loop), LVDS serializers. (`devg-nvtmon`
   now finds an NCT1008-compatible sensor at DVC 0x4c; gtf2 still logs one
   `Can't open /dev/nvtmon/...` because its first poll runs before Stage3
   starts `devg-nvtmon`, and later polls succeed.)
3. `/var/swdl` missing for swdlclient; `devf` finds no flash device.
4. Frequent unimplemented CAR reads (0x8c, 0x9c, 0xbc, 0x30c, ...) and
   APB_MISC offset 0x324c polling; not yet linked to a failure.

These are runs with a synthetic bootloader handoff, board identity, NOR and
eMMC layout; they show the original Stage1/2/3 scripts and binaries executing,
not a faithful FPK1 board model.

## Graphics: host1x fixes and the MHI2 GLES forwarding port

### Native path (no shim)

A login shell (`run_stage1_console.py --shell`, or `--diag-shell` which swaps
the final `tinit` record for `ksh` in the in-memory boot script) showed
`kdgui_2dmgr` REPLY-blocked on `devg-nvrm`, whose threads wait for a syncpoint.
The host1x model stalled channels on GR3D (class 0x60) methods and on
`WAIT_SYNCPT_BASE`, and never resumed a channel stalled on a wait. Fixes in
`hw/misc/tegra30_host1x.c`: `WAIT_SYNCPT_BASE`, re-running stalled channels on
any syncpoint increment, and dropping unknown host1x-class methods (INDOFF/
INDDATA indirect GR3D register traffic, module 6). With
`TEGRA_GR3D_DISCARD=1`, GR3D jobs retire (INCR_SYNCPT only): `kdgui_2dmgr`
starts, `gtf2` creates its 1440x540 window, and dc-a scans out a black frame.
GR3D itself is not emulated.

### GLES forwarding as on MHI2

MHI2 keeps the native KD/CWM/NvRm stack and replaces only `libEGL.so` and
`libGLESv2.so` with `tools/mhi2/glforward/guest/gl_shim.c`, forwarding GLES
over an MMIO aperture to `glhost` (Mesa/NVIDIA EGL on the host). FPK1 uses the
same NVIDIA QNX BSP (17.52 MMX2) and the same EAL engine.

- `hw/arm/fpk1.c` now has the same optional `glbridge` transport
  (`-chardev ...,id=glbridge`; MMIO 0x5f000000, bulk RAM 0x5e000000).
- The shim builds with `arm-none-eabi-gcc`; FPK1 binaries import 109
  EGL/GLES symbols and the shim exports all of them. `GLBRIDGE_DEFAULT_W/H`
  (1440x540 for FPK1) set its surface size; `glhost` takes
  `MHI2_GL_WIDTH/HEIGHT` because clients are selected before `eglInitialize`.
- `patch_stage2_files.py` replaces files inside STAGE2.1 of the synthetic NOR.
  liblzo2's LZO1X-999 reproduces the original block sizes (lzokay is ~7%
  larger and does not fit). Only the run of blocks around the edits (12 of 37)
  is re-packed into the same slots; the imagefs checksum is rebalanced in the
  freed file space, so the table, stored size and other bytes are unchanged,
  and the result is verified by decoding.
- `run_stage1_console.py --stage2-replace lib/libEGL.so=... --glhost ...`
  starts `glhost` on a pipe chardev, as `tools/mhi2/debug_shell_local.py`.

Measured (TEGRA_GR3D_DISCARD=1, board cmdline, synthetic eMMC):

- `gtf2` (EAL) runs through the shim: 48 NVIDIA shader binaries
  (`GL_NVIDIA_PLATFORM_BINARY_NV`, from `libeal.so` and `.kzb` resources),
  textures and programs reach `glhost`. 47 match MHI2's existing Audi EAL
  translations (`audi_shaders.h`). The remaining fragment program
  (hash `f9b134a4613cf687`, 816 bytes, `vTexCoord`/`Color`/
  `LayerRenderTexture`, used by `Materials/displaySupervisor`) loads from an
  `MHI2_SHADER_CACHE` file with a guessed `texture*Color`; this translation is
  **unverified** against the Tegra instruction stream.
- `gtf2` issues no draw or swap; only `glhost`'s own clear reaches the frame.
  `kdgui_2dmgr` sends `eglInitialize` and then disappears without console
  output; `gss_ipc` reports `hmi` and `kdgui_2dmgr` failed to start-up and the
  Stage3 fallback follows. Started by hand after boot it fails with
  `nvdcGetWindow failed` (window already owned). Its failure under the shim is
  the next blocker.
- One run (with shell activity and per-client dumps) ended in a QNX kernel
  shutdown listing `gtf2`/`traceserver`; two repeats without them did not.
- Killing a bridge client while it holds the record lock (register 16) leaves
  the lock taken; later clients then spin. This is inherited from the MHI2
  transport.

```sh
arm-none-eabi-gcc -mfloat-abi=soft -mcpu=cortex-a9 -marm -fPIC -ffreestanding \
  -fno-builtin -O2 -DGLBRIDGE_DEFAULT_W=1440 -DGLBRIDGE_DEFAULT_H=540 \
  -c tools/mhi2/glforward/guest/gl_shim.c -o /tmp/gl-shim.o
arm-none-eabi-ld -shared --hash-style=sysv -soname libEGL.so -o /tmp/libEGL.so /tmp/gl-shim.o
arm-none-eabi-ld -shared --hash-style=sysv -soname libGLESv2.so -o /tmp/libGLESv2.so /tmp/gl-shim.o
bash tools/mhi2/glforward/build_host.sh /tmp/glhost
MHI2_GL_WIDTH=1440 MHI2_GL_HEIGHT=540 TEGRA_GR3D_DISCARD=1 \
python3 tools/fpk1/run_stage1_console.py <firmware.zip> \
  --qemu ./build-fpk1/qemu-system-arm --icount-shift 0 --board-info \
  --emmc /tmp/fpk1-emmc.img --stage2-replace lib/libEGL.so=/tmp/libEGL.so \
  --stage2-replace lib/libGLESv2.so=/tmp/libGLESv2.so --glhost /tmp/glhost \
  --seconds 120 --json /tmp/fpk1-gl.json
```

### Why kdgui_2dmgr exited under the shim

A diagnostic shim build (`-DGLBRIDGE_TRACE -finstrument-functions`) logs the
first 300 shim calls per process to the console as offsets from
`glbridge_trace_anchor` (map with `nm`; libEGL and libGLESv2 are separate
copies of the same object, so calls into the other copy show as large
offsets). `kdgui_2dmgr` called `eglGetDisplay`, `eglInitialize`,
`eglChooseConfig`, `eglCreateContext`, `eglMakeCurrent`, then
`eglDestroyContext`/`eglTerminate`. At 0x10af4c it requires
`EGL_KHR_image`, `EGL_KHR_gl_texture_2D_image` and `GL_OES_EGL_image`; the shim
advertised only the first and returned an empty `GL_EXTENSIONS`, so it logged
"EGL does not support EGL_KHR_gl_texture_2D_image extension" to its trace
logger (not the console) and exited.

The shim now advertises both extensions and implements
`EGL_GL_TEXTURE_2D_KHR` images: binding such an image with
`glEGLImageTargetTexture2DOES` sends op 140, and `glhost` makes the target
texture id an alias of the source's host texture (one host context per guest
process). Rejected NvRm surface images are logged with their fields.

Result: `kdgui_2dmgr` stays up, creates its NvRm surface images and serves
`gtf2` a CWM window (`glbridge: CWM window beeb0000 publishes 1440x540`); it
is no longer listed by `gss_ipc` as failed. Two of its own shader binaries
(`c15b5c368e434418`, `23522ab1913cc1e6`) have no translation yet.

### Next blocker: CSI capture GPIO

`kdgui_2dmgr` still never creates `/dev/sem/kdgui_2dmgr_ready` (also not
without the shim), so `gtf2` loads assets but never draws and `hmi` fails
start-up. Its capture layer reports
`CAL: unable to connect to GPIO_Interrupt /dev/nvgpio/csi_pass...giving up`.
`devg-nvgpio`'s FPK table (27 entries of 0x34 bytes: name, pin, flags)
ends with `csi_lock` (K2) and `csi_pass` (I5), but only entries 0..24 appear
under `/dev/nvgpio`. With `TEGRA_GPIO_DEBUG=1` (new stderr trace of GPIO
writes) the driver configures K2 and I5 as GPIO inputs with `INT_LVL`/
`INT_CLR` writes and interrupts masked; `pidin irqs` shows a single attached
vector 0x165. The interrupt-pin publication path, and whether the GPIO bank
interrupt routing in the Tegra30 model satisfies it, are the next step.

### csi_pass: board revision, not emulation

`devg-nvgpio` selects its pin table from `/dev/nvsku`: SKU 5 gives the
27-entry FPK table (0x34-byte records: name, pin, flags). At 0x101e94 it then
truncates that table at `csi_lock` for project 0xf19c when the board revision
(nvsku field 3) is below 600 (0x258), dropping `csi_lock` (K2) and `csi_pass`
(I5). Our synthetic revision 200 caused this. With revision 600
(`BOARD_CMDLINE` now `699-61852-0005-600`), `/dev/nvgpio/csi_lock` and
`/dev/nvgpio/csi_pass` exist, the CAL fatal error disappears and
`kdgui_2dmgr` creates `/dev/sem/kdgui_2dmgr_ready`; `gtf2` no longer reports
`Bad path 'kdgui_2dmgr_ready'`. The real revision is still unknown; 600 is the
minimum that keeps the CSI pins. (An off-by-one in our PLT name mapping first
mislabelled the imports; capstone prints ARM rotated immediates as a second
`#n`.)

### Shader translations from the GR3D stream

The platform shader binaries embed the host1x GR3D upload stream (vertex
program via method 0x206, fragment program from method 0x541).
`tools/fpk1/tegra_shader_disasm.c` feeds it to grate's libcgc disassembler.
`tools/fpk1/gl_shaders/` holds `MHI2_SHADER_CACHE` translations for the three
binaries without an MHI2 entry (status per file in its README); the
`kdgui_2dmgr` vertex program is transcribed instruction by instruction, the
fragment programs are approximate.

### Next blocker: gss_ipc's SPI link to KSS

`gtf2` still issues no draws and `hmi` fails start-up. Its threads wait on
`kdgui_2dmgr`, `broker` and `gss_ipc`; `gss_ipc` reports
`IPC NOT RUNNING! (Transfer loop is hanging for more than 5000 ms)` in every
run. Two of its threads sit in INTR on the Tegra SPI slave used through
`libnvspislave` (`NvSpiSlaveInit`, `NvSpiSlaveTransferData`): the link to
the KSS side of the cluster, which is not emulated. Its `spisimulation`
option prints "SPI simulation not built in" in this production build. A KSS
peer on the SPI slave controller (and its framing) is the next work item.

## KSS: the cluster's second processor and its SPI link

### KSS image

`kss-application/.../KSSApplication.bin` is the firmware of the KSS
microcontroller. `tools/fpk1/decompress_kss.py` decodes it: the HSP payload
(offset and sizes from its SignInfo) is LZSS with a flag byte per eight
tokens (most significant bit first; 0 literal, 1 two-byte reference with
length `b0 >> 2` and distance `((b0 & 3) << 8) | b1`). Decoding consumes the
whole stored payload (599,730 bytes) and yields exactly the declared
1,048,564 bytes. The image is 32-bit ARM code linked at 0x01000000: word 0 is
`ldr pc, [pc, #-4]` loading 0x01000008, which sets up the mode stacks near
0xe7xx and jumps to Thumb code at 0x0100087d. Flash at 0x01000000 with RAM at
0 fits Cortex-R-class automotive MCUs; the exact part is not identified.

Strings show KSS supervising the Tegra side ("GSS IPC ready.",
"GSS HMI run request.", "GSS Sound run request.",
"GSS NAND maintenance run request.", "GSS startup stuck", "GSS Reset
Requested"). This matches the Tegra logs: `gss_ipc` reports
`IPC NOT RUNNING!` and `gtf2` (`hmi`) never starts because nothing on the
KSS side requests it.

### Tegra side

`gss_ipc` uses `libnvspislave` as SPI slave (transport class
`GSS_IPC_SpiNv`, 128-byte buffers). Above it are channels/CIDs (GSS-Manager
`gssModeRequest`/`gssModeResponse` with a 16-byte payload,
`gssResetRequest` 8 bytes, `sysModeRequest`, `gssAliveRequest`,
`KssStatus`, ping with a watchdog, BAP, diagnosis, trace). The library maps
CAR (0x60006000), APB_MISC (0x70000000), GPIO (0x6000d000) and SLINK1
(0x7000d400) directly:

- SLINK1 interrupt is vector 0x5b (91); its thread reads the RX FIFO count
  from STATUS2 bits 21:16, moves 64 bytes per interrupt between the
  RX (+0x180) / TX (+0x100) FIFOs and its buffers, and re-arms by writing
  STATUS bits 26/27; STATUS bit 29 is checked as an error.
- The handshake uses GPIO CC6 (`hsk_to_kss`, driven by Tegra) and DD7
  (`hsk_to_gssn`, an edge interrupt from KSS) through the GPIO controller's
  masked registers; `start_mode_to_gss` tells `gss_ipc` the KSS mode
  ("KSS Application mode").
- QEMU has no SLINK model; earlier logs show these accesses as
  `unimplemented-memory` at 0x7000d400..0x7000d500.

### Next steps

1. Recover the frame format above the 64/128-byte SPI transfers from
   `gss_ipc` (header, CID, length, CRC) and the start-up exchange that leads
   KSS to send "GSS HMI run request".
2. Model SLINK1 in slave mode (FIFOs, STATUS/STATUS2, interrupt 91) with a
   chardev to an external KSS peer, plus the CC6/DD7 handshake lines.
3. Write a minimal host KSS peer that answers the start-up and alive
   messages and issues the HMI run request.

### gss_ipc frame format above SPI

Recovered from `gss_ipc`'s Transfer, RxBuffers and TxBuffers code (now
encoded in `tools/fpk1/gss_ipc_frames.py` with firmware-free tests):

- One 128-byte frame per direction per transfer (`GSS_IPC_SpiNv` reports
  0x80). Byte 0 = used payload bytes; records in bytes 1..126; unused bytes
  0xff; byte 127 = `~sum(bytes[0:127]) & 0xff` (0x15a288). An empty frame is
  0x00, 126 x 0xff, checksum.
- Record = `[fragment length][LUN][CID | 0x80 on the last fragment]` +
  fragment. Byte 0 includes the 3-byte headers. RxBuffers reassembles per
  LUN/CID and calls the registered handler on the last fragment.
- Per cycle: get next TX frame -> `setTxData` -> `transferData` (RX frame)
  -> checksum check -> `transferAck` exchanging one byte, 0xd0 ACK or 0xe1
  NACK. Only when both bytes are 0xd0 is the TX frame released and the RX
  frame processed; otherwise both are retried.

Other services also register LUNs (ping/echo, diag, FDS around 0x13,
tracing/DDT around 0x12, SWDL 0xff, a BAP/HMI LUN 0x11); only the
GSS-Manager registration on LUN 7 was disassembled in full:

| Direction | CID | Message | Payload |
| --- | --- | --- | --- |
| KSS -> GSS | 3 | GSS_MODE_REQUEST | mode, submode, <= 16 persistency bytes |
| KSS -> GSS | 6 | GSS_FLASH_RESPONSE | 2 |
| KSS -> GSS | 8 | GSS_KSS_STATUS | 1 |
| KSS -> GSS | 9 | SYS_MODE_REQUEST | 3 |
| KSS -> GSS | 11 | GSS_ALIVE_REQUEST | 1 (answered at once) |
| GSS -> KSS | 1 | GSS_STATUS | 1 ("IPC COM ready") |
| GSS -> KSS | 2 | GSS_RESET_REQUEST | |
| GSS -> KSS | 4 | GSS_MODE_RESPONSE | mode, submode, 16 persistency bytes |
| GSS -> KSS | 12 | GSS_ALIVE_RESPONSE | 1 |

In GSS_MAN_GssManager (0x141178) mode 1 dispatches on submode: 0 stores the
16 persistency bytes, 2 enters `GSS_SM_APP_RUN` (`Rte_Start`, application
run); mode 2 stops; modes 3/4 query state. Every request is answered with
GSS_MODE_RESPONSE. The minimal KSS start-up is therefore expected to be:
answer the GSS_STATUS, send GSS_MODE_REQUEST(1, 2, persistency) and keep
answering alive/ping traffic. This sequence is inferred from code, not yet
observed working.

`tools/fpk1/qnx_elf_disasm.py` is the PLT-aware disassembler used for this
(QNX binaries have no section headers; ARM immediates are decoded from the
encoding).

## First rendered FPK1 screen

With the GLES bridge, the Stage3 service application `grengme` (started on
the gtf2 fallback path) renders its service menu: a green frame with the
title "Main" and the entries "Debugging" and "GSS". `glhost` writes it to
`/tmp/mhi2-client-<pid>.ppm` with `MHI2_GL_DUMP_CLIENTS=1`; it is not on the
display controller, because `kdgui_2dmgr`, which composes client windows,
does not compose without the KSS run request.

Two fixes to the 2D compositor fragment translation
(`tools/fpk1/gl_shaders/23522ab1913cc1e6-948.glsl`) were needed, found by
decoding a `MHI2_GL_CAPTURE` stream:

- `alphaTex` is set with `glUniform1i` (1 for GL_ALPHA glyph textures, 0 for
  RGBA icons). Declared as `float`, the call failed and glyphs were drawn as
  premultiplied black; it is now a `bool`.
- Blend mode 1 expects premultiplied output; without it transparent glyph
  texels were drawn as solid squares.

Glyphs are uploaded as small GL_ALPHA textures with unaligned rows
(e.g. 11x16), so the guest's `glPixelStorei(GL_UNPACK_ALIGNMENT, 1)` matters.
Uniform locations in this program: alphaTex, aspect, modulateColor, quad,
rotation, texRect, sampler (host-assigned order).

The fpk1 glbridge now releases the record lock after 2 s of guest time
without accesses by its holder (lock polling by waiters does not extend it)
and drops unread reply bytes, so a client killed mid-record no longer blocks
every other client. `tools/fpk1/check_glbridge.py` checks this with qtest.

### Viewing rendered frames

The display path is unchanged; frames are shown on the host instead.
`run_stage1_console.py --gl-frames DIR` makes `glhost` write the primary frame
(`DIR/primary.ppm`) and one dump per guest client (`DIR/mhi2-client-<pid>.ppm`,
via the new `MHI2_GL_CLIENT_DIR`); `--viewer` also opens
`tools/fpk1/view_frames.py` on that directory. The viewer (PySide6, reusing
MHI2's `FrameView`) lists the sources, follows the most recently updated one
unless a source is chosen, and only displays complete PPMs (glhost writes them
atomically). `view_frames.py --snapshot out.png` saves the newest frame
headless, e.g. with `QT_QPA_PLATFORM=offscreen`. On Ubuntu it needs
`python3-pyside6.qtcore`, `python3-pyside6.qtgui` and
`python3-pyside6.qtwidgets`. With a 135 s run, grengme's service menu is the
newest client frame.

`displaySupervisor` (`f9b134a4613cf687`) is now translated from its GR3D
program: texture red times `Color.a` scales `Color.rgb`, alpha 1.0, no
render-target load. It compiles and links; gtf2 does not draw yet, so it has
not been seen on screen.

## Steering-wheel buttons: path to the HMI

How the buttons reach the cluster software (static analysis plus runs with
`--diag-shell`):

- KSS receives the CAN signal `MFL_Tasten_Kon_01` (`MFL_Tastencode_1/2`,
  `MFL_Eventcode_1/2`, `MFL_Marke`, `MFL_Variante`, one byte each in
  `gss_ipc`'s trace formatter) and forwards it over the SPI link. `gss_ipc`
  keeps it in its RTE (`RTE incoming event: MFL_Tasten_Kon_01`,
  `Rte_Read_MFL_Tasten_Kon_01_...`) and passes it on through the comm service
  `asi.gss.ipc.rte.hmi.IHmiKss` ("data ignored, since client not connected"
  when no HMI client is attached).
- `gtf2` is that client. `GSS_APP_KeyEventConverter` handles
  `handleKeyEventMfl(keycode1, evcode1, keycode2, evcode2)`, maps each keycode
  through a table ("MFL keycode=..., idx, is_but, ev_id, ticks"; unknown codes
  are logged) and dispatches buttons and roller ticks to the HMI, telephone,
  warnings, MFL config, or the engineering menu. MMI CAN key, joystick and
  touchpad messages use the same converter.
- The engineering menu (`grengme`) gets its keys from `gtf2`: `gtf2` provides
  `gem.KeyInput` (`GSS_HMI_GTF2_GEMKeyInputServiceImpl`, `GSS_APP_GemHandler`:
  OK, BACK, roller UP/DOWN with ticks) and opens GEM on an MFL key combination
  (`detectMflKeyCombination`). `grengme`'s console key backend
  (`libengmenufw`, '4'/'6' roller, '5' select, '0' back) is disabled by
  `/config/gem.json` (`"consoleInput":false`), and its stdin is not the serial
  console anyway (`pidin` shows fd 0 on procnto, as for any background job of
  the non-interactive Stage3 script). Bytes on the serial console go to the
  login shell; none of `grengme`'s threads reads `/dev/ser1`.
- `gtf2` itself is started by `gss_ipc`'s manager through
  `asi.gss.manager.hmi.IGssMan2HMI` (`GssMan2HMIReplyImpl::activate()`),
  which needs the KSS run request (GSS_MODE_REQUEST 1/2 on LUN 7).

So without patching, buttons need the KSS peer: model SLINK1 and the CC6/DD7
handshake, have a host KSS peer bring `gss_ipc` up and request application
run, then send `MFL_Tasten_Kon_01` updates when buttons are pressed. Still
open: the LUN/record layout of RTE signal updates in `gss_ipc`, and the MFL
keycode table in `gtf2`. `stage3/bin/app/gssipc-kbd` (a firmware test tool
linked against the IHmiKss and BAP proxies, printing
"Key1 %d, Event1 %x, Key2 %d, Event2 %x") is a reference for the expected
values.

## SLINK1 slave model and a host KSS stand-in: gtf2 starts

### libnvspislave protocol

Recovered from `lib/libnvspislave.so` (Stage2.1):

- It maps SLINK1 (0x7000d400), GPIO, APB_MISC and CAR directly. Pins are
  named in its init data: DD7 is the input from KSS (interrupt vector
  `0xa0 + gpio`, polarity flipped after every interrupt so both edges are
  seen), CC6 the output to KSS.
- SLINK is used in packed PIO mode with the RX-complete interrupt (vector 91):
  TX/RX FIFO at +0x100/+0x180, STATUS2 bits 21:16 give the RX word count (16
  words = 64 bytes, anything else is read as one byte), DMA_CTL bit 31 starts
  a transfer and clears when it completes, STATUS bits 26/27 flush TX/RX and
  0x230d0000 clears the error bits.
- `NvSpiSlaveTransferData` moves a 128-byte frame in two 64-byte halves,
  `NvSpiSlaveTransferAck` one byte. Seen from the master: raise DD7; when CC6
  rises clock 64 bytes; when CC6 falls clock 64 bytes; when CC6 rises clock
  the ACK byte; when CC6 falls drop DD7. DD7 falling mid-transfer aborts it.
  The Tegra raises CC6 with DD7 low to request a cycle when it has data.

### Model and peer

- `hw/misc/tegra30_slink.c` (`tegra30-slink`, FPK1 machine only) implements
  that subset as a slave. The master is an external process on
  `-chardev ...,id=kss`, with a small byte protocol (`D` level for DD7,
  `X n data` to clock n bytes; `C` level for CC6, `R n data` back). CC6 and
  DD7 are wired through the existing GPIO model.
- `tools/fpk1/kss_peer.py` is the master: it runs the handshake every 10 ms,
  speaks the gss_ipc frame format, answers `GSS_STATUS 1` ("IPC COM ready")
  with `GSS_MODE_REQUEST(1, 2)` and sends `GSS_ALIVE_REQUEST` every second.
  `run_stage1_console.py --kss` starts it and keeps its log as `kss.log`;
  with `--viewer` (always the case in `run.sh`) it runs inside
  `view_frames.py --kss`, which shows the log under the frame.

### Result

The link runs from the first second: `gss_ipc` answers with
`GSS_MODE_RESPONSE 01 02`, its status goes 1 -> 7 -> 5/6, it sends RTE/HMI
traffic on LUN 0x11 (records starting with `ba be`) and a trace record on
LUN 0x12, and `gtf2` is activated: it logs its configuration
(`SW_GSS_Version: C1_AU736_0378_1280_prod`), loads Kanzi materials and
draws its first frame through the GLES bridge, a black screen with the
version overlay (`--:--`, `1.1.2012`, the software version). In a 240 s
run the link made 7816 cycles (7758 frames delivered; the rest were retried
while `gss_ipc` was busy). The cluster itself is not drawn yet: gtf2 loads its
Kanzi materials and glhost has no translation for 243 distinct shaders
(`UNSUPPORTED NVIDIA shader hash=...` in glhost.log), and the peer sends no
vehicle (RTE) data, so `gss_ipc` keeps logging
`Rte_Read_VersionsScreen_VS_VersionInfo returned 1`. The GSS AliveManager
sends one `GSS_RESET_REQUEST` (component 2, reason 6) after `audio_player`
fails on its DAC; the peer only logs it.

### Link abort deadlock (fixed)

Later runs ended with the peer logging `link: stuck in first (CC6=1),
dropping DD7` every 2.5 s for the rest of the run. The model stopped reading
the chardev while an `X` waited for the slave to arm, so the peer's `D 0`
(its abort after a 2 s stall) never reached the guest: DD7 stayed high, no
edge came, and the waiting `X` was never armed. The model now always reads
the chardev, and `D 0` drops a waiting `X`. In a 150 s run the link made
11190 cycles (11182 frames delivered). An isolated stall at 16.8 s cleared on
the next cycle, and `GSS_RESET_REQUEST` (component 2, reason 6) now arrives.
The remaining `stuck in first (CC6=0)` lines are from before `gss_ipc` starts
(about 2 s) and from after the guest kernel shuts down (`Shutdown[0,3] ...
lock exit 1` at about 135 s), which is a separate problem.

### RTE signals over l4c: VS_VersionInfo (fixed)

`Rte_Read_VersionsScreen_VS_VersionInfo returned 1!` came from start-up, not
from missing traffic later on: on `GSS_SM_APP_RUN` gss_ipc calls `Rte_Start`
and then "Update HOOK from RTE..." (0x1295a4), which reads RTE message 0x75
once. `Rte_Read` (0x162578) returns per-signal status bits, and bit 0
(bitmap 0x1cbb14, all set at init) means "never received". The peer sent the
run request before any RTE data, so the read always failed.

KSS delivers RTE data on LUN 0x11 (CIDs 0/1) as a byte stream of l4c
messages (header built at 0x162b40, parsed at 0x1637a4): `ba be`, 14-bit
payload length and 2-bit priority, 12-bit dataID (low nibble 0), CRC-8 of
the payload (polynomial 0x1d, initial value 0; checked on receive). The
dataID table at 0x1abdf0 (20-byte entries) gives the signal length and a
callback; the byte after the signal is the status that the callback passes
to `Rte_Write`. VS_HMI_VersionsInfo is dataID 0x24d, 56 bytes (unpacker
0x167f0c: flags, zpm_version and zpm_version_db big endian, coding[15],
TeileNum[11], hw_TeileNum[11], sw[4], kss_sw[4], hw[3], Flashdatum[3]).

`kss_peer.py` now sends VS_HMI_VersionsInfo (stand-in part number
8S0906961AK, software 0378, status 0) on IPC ready, and sends
`GSS_MODE_REQUEST(1, 2)` 0.2 s after that frame is delivered. In a 40 s run
the error is gone and gtf2 starts as before.
