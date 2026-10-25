#!/usr/bin/env python3
"""Verify the observed Q7 SIFS table and framed LZO parts, in memory only.

Research profile, not a general SIFS specification. Offsets start at CIFS
(raw member +0xba), unlike older probes starting eight bytes later.
Optional LZO decoding requires lzokay; checksums need only the standard library.
"""
import hashlib
import struct
import zipfile
import zlib

WRAPPER = 0xba
MAGIC = 0x41303200
MAX_BLOCK = 16 * 1024 * 1024
MAX_IMAGE = 128 * 1024 * 1024


def words(data, at, count):
    if at < 0 or at + count * 4 > len(data):
        raise ValueError("Truncated SIFS structure")
    return struct.unpack_from(f"<{count}I", data, at)


def parse_table(data, at=0x800):
    if data[at:at + 8] != b"IFSPTTBL":
        raise ValueError("Missing IFSPTTBL")
    version, count, size = words(data, at + 8, 3)
    if version != 2 or not 1 <= count <= 16:
        raise ValueError("Unsupported table version or partition count")
    end = at + 32 + size
    if size > 4096 or end > len(data):
        raise ValueError("Invalid partition table extent")
    cursor = at + 32
    partitions = []
    for _ in range(count):
        if cursor + 12 > end:
            raise ValueError("Truncated partition record")
        name = data[cursor:cursor + 8].rstrip(b"\0").decode("ascii")
        number, = words(data, cursor + 8, 1)
        if not 1 <= number <= 4 or cursor + 12 + 32 * number > end:
            raise ValueError("Invalid part count or extent")
        cursor += 12
        parts = []
        for _ in range(number):
            storage, compressed, offset, stored, logical, chunk, r0, r1 = words(data, cursor, 8)
            if storage not in (0, 1) or compressed not in (0, 1):
                raise ValueError("Unsupported part storage or compression flag")
            parts.append(dict(storage=storage, compressed=bool(compressed), offset=offset,
                              stored_size=stored, logical_size=logical, chunk_size=chunk,
                              reserved=[r0, r1]))
            cursor += 32
        partitions.append(dict(name=name, parts=parts))
    if cursor != end:
        raise ValueError("Partition records do not match table byte count")
    return dict(version=version, table_offset=at, table_bytes=size,
                data_base=end, partitions=partitions)


def verify_part(data, start, part, decompress=False):
    stored = part["stored_size"]
    if start < 0 or stored <= 0 or start + stored > len(data):
        raise ValueError("Part outside member bounds")
    if not part["compressed"]:
        raw = data[start:start + stored]
        return dict(blocks=0, output_size=len(raw), sha256=hashlib.sha256(raw).hexdigest()), raw
    chunk = part["chunk_size"]
    if not 16 < chunk <= MAX_BLOCK:
        raise ValueError("Invalid compressed chunk size")
    output = bytearray()
    digest = hashlib.sha256()
    total = 0
    blocks = 0
    for rel in range(0, stored, chunk):
        at = start + rel
        checksum, magic, compressed, logical = words(data, at, 4)
        if magic != MAGIC or compressed == 0 or compressed + 16 > min(chunk, stored - rel):
            raise ValueError(f"Invalid block header at {at:#x}")
        if not 0 < logical <= MAX_BLOCK or total + logical > MAX_IMAGE:
            raise ValueError("Block output exceeds limit")
        frame = data[at + 4:at + 16 + compressed]
        if zlib.adler32(frame) & 0xffffffff != checksum:
            raise ValueError(f"Block checksum mismatch at {at:#x}")
        if decompress:
            import lzokay
            decoded = lzokay.decompress(data[at + 16:at + 16 + compressed], logical)
            if len(decoded) != logical:
                raise ValueError("LZO output size mismatch")
            digest.update(decoded)
            output.extend(decoded)
        total += logical
        blocks += 1
    if total != part["logical_size"]:
        raise ValueError("Part logical size mismatch")
    return dict(blocks=blocks, checksums_verified=blocks, output_size=total,
                lzo_verified=decompress, sha256=digest.hexdigest() if decompress else None), bytes(output)


def member(archive, suffix, signature):
    matches = [n for n in archive.namelist() if n.endswith('/' + suffix)]
    if len(matches) != 1:
        raise ValueError("Expected exactly one " + suffix)
    raw = archive.read(matches[0])
    if raw[:3] != b"HSP" or raw[WRAPPER:WRAPPER + len(signature)] != signature:
        raise ValueError("Unexpected HSP member profile: " + suffix)
    return raw[WRAPPER:]


def verify_archive(path, decompress=False, *, inspect_image=None):
    if inspect_image is not None and not decompress:
        raise ValueError("Image inspection requires complete decompression")
    with zipfile.ZipFile(path) as archive:
        nor = member(archive, "stage2_ifs.img", b"CIFS")
        nand = member(archive, "stage2_nand.img", b"ESO_BIN\0")
    table = parse_table(nor)
    # Observed update-member to flash mapping; verified by all block checksums.
    nand_flash_base = 0x200000
    images = []
    for partition in table["partitions"]:
        results = []
        image = bytearray()
        for part in partition["parts"]:
            data = nor if part["storage"] == 0 else nand
            start = (table["data_base"] + part["offset"] if part["storage"] == 0
                     else part["offset"] - nand_flash_base)
            report, decoded = verify_part(data, start, part, decompress)
            results.append(dict(payload_offset=start, raw_member_offset=WRAPPER + start,
                                **part, **report))
            if len(image) + len(decoded) > MAX_IMAGE:
                raise ValueError("Combined image exceeds limit")
            image.extend(decoded)
        complete = decompress or not any(p["compressed"] for p in partition["parts"])
        imagefs_size = None
        if complete:
            if image[:8] != b"imagefs\x04":
                raise ValueError("Reconstructed imagefs header mismatch")
            imagefs_size, = words(image, 8, 1)
            if imagefs_size != len(image):
                raise ValueError("Reconstructed imagefs size mismatch")
        inspection = inspect_image(bytes(image)) if inspect_image is not None else None
        images.append(dict(name=partition["name"], parts=results,
                           imagefs_size=imagefs_size,
                           imagefs_sha256=hashlib.sha256(image).hexdigest() if complete else None,
                           **({"inspection": inspection} if inspect_image is not None else {})))
    return dict(profile="Q7 0378; CIFS-relative coordinates", wrapper_bytes=WRAPPER,
                table={k: v for k, v in table.items() if k != "partitions"},
                nand_flash_base=nand_flash_base, images=images,
                limitations=["NAND flash base is inferred for this update, not a universal constant.",
                             "Integrity and LZO checks do not demonstrate QNX boot or device emulation."])
