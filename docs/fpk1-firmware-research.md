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
