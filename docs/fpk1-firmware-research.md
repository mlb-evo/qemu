# FPK1 firmware reverse-engineering notes

Status: preliminary research, **not a bootable FPK1 machine**. Source: user-supplied Audi Q7 2018 update archive `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip`. No proprietary firmware binaries committed.

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
