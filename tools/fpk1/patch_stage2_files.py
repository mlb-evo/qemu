#!/usr/bin/env python3
"""Replace regular files inside STAGE2.1 of a Stage2 CIFS payload (diagnostic).

Only the observed Q7 profile is supported: STAGE2.1 is a single compressed NOR
part whose LZO blocks occupy fixed chunk-sized slots but carry their own
logical sizes. A replacement must not be larger than the original file; its
catalog size is updated and the imagefs additive checksum is rebalanced
in the freed space after a replacement.
Blocks are re-encoded with liblzo2's LZO1X-999, which reproduces the original
compressed sizes (lzokay is ~7% larger and is only a fallback). A run of
adjacent blocks around the edits is re-packed into the same slots, widened
until it fits. Slot positions, the stored size, the table and all bytes
outside the run stay identical. Decoding needs lzokay. Output is in memory.
"""
import ctypes
from pathlib import Path
import struct
import sys
import zlib

from inspect_stage2_catalogs import parse_catalog
from verify_sifs_partitions import MAGIC, parse_table, verify_part


def _decode_blocks(payload, start, part):
    import lzokay
    blocks = []
    for rel in range(0, part['stored_size'], part['chunk_size']):
        at = start + rel
        _, magic, compressed, logical = struct.unpack_from('<4I', payload, at)
        if magic != MAGIC:
            raise ValueError(f'Invalid block header at {at:#x}')
        blocks.append((at, lzokay.decompress(payload[at + 16:at + 16 + compressed], logical)))
    return blocks


def _lzo1x_999():
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'mhi2'))
        from lzo_library import load_lzo2
        return load_lzo2()
    except OSError:
        return None


_LZO = _lzo1x_999()


def _compress(data):
    if _LZO is None:
        import lzokay
        return lzokay.compress(data)
    out = ctypes.create_string_buffer(len(data) + len(data) // 16 + 67)
    size = ctypes.c_ulong(len(out))
    work = ctypes.create_string_buffer(14 * 16384 * 8)  # LZO1X_999_MEM_COMPRESS on LP64
    if _LZO.lzo1x_999_compress(data, ctypes.c_ulong(len(data)), out, ctypes.byref(size), work):
        raise ValueError('lzo1x_999_compress failed')
    return out.raw[:size.value]


def _encode_block(data):
    body = _compress(data)
    frame = struct.pack('<3I', MAGIC, len(body), len(data)) + body
    return struct.pack('<I', zlib.adler32(frame) & 0xffffffff) + frame


def _pack(data, slots):
    """Greedily fill ``slots`` (byte capacities); None if the data does not fit."""
    blocks, cursor = [], 0
    for index, capacity in enumerate(slots):
        remaining = len(data) - cursor
        if index == len(slots) - 1:
            block = _encode_block(data[cursor:])
            return blocks + [block] if len(block) <= capacity else None
        # Bisect the largest prefix that fits; edits are rare, so speed is secondary.
        # Leave at least one byte for each later slot: every slot needs a block.
        low, high, best = 1, remaining - (len(slots) - index - 1), None
        while low <= high:
            middle = (low + high) // 2
            block = _encode_block(data[cursor:cursor + middle])
            if len(block) <= capacity:
                best, low = (middle, block), middle + 1
            else:
                high = middle - 1
        if best is None:
            return None
        blocks.append(best[1])
        cursor += best[0]
    return None


def patch_stage2_1(payload, replacements):
    """Return (new CIFS payload, report) with ``{path: bytes}`` replaced."""
    table = parse_table(payload)
    partition = next(p for p in table['partitions'] if p['name'] == 'STAGE2.1')
    if len(partition['parts']) != 1:
        raise ValueError('Unsupported STAGE2.1 layout')
    part = partition['parts'][0]
    if part['storage'] != 0 or not part['compressed']:
        raise ValueError('STAGE2.1 must be one compressed NOR part')
    start = table['data_base'] + part['offset']
    blocks = _decode_blocks(payload, start, part)
    image = bytearray(b''.join(data for _, data in blocks))
    entries = {e['path']: e for e in parse_catalog(bytes(image))['entries']}
    report, spare = [], None
    for path, data in replacements.items():
        row = entries.get(path)
        if row is None or row.get('kind') != 'regular':
            raise ValueError(f'No regular file {path} in STAGE2.1')
        if len(data) > row['size']:
            raise ValueError(f'Replacement for {path} is larger than the original')
        image[row['offset']:row['offset'] + row['size']] = data + bytes(row['size'] - len(data))
        struct.pack_into('<I', image, row['record_offset'] + 28, len(data))
        report.append(dict(path=path, original_size=row['size'], new_size=len(data)))
        aligned = (row['offset'] + len(data) + 3) & ~3
        if aligned + 4 <= row['offset'] + row['size']:
            spare = aligned
    # Rebalance the additive checksum in freed file space rather than in the
    # trailer, so the final block (and the run reaching it) stays untouched.
    if spare is None:
        spare = len(image) - 4
    total = sum(x[0] for x in struct.iter_unpack('<I', image)) & 0xffffffff
    word, = struct.unpack_from('<I', image, spare)
    struct.pack_into('<I', image, spare, (word - total) & 0xffffffff)
    parse_catalog(bytes(image))  # re-validate extents after the edit

    offsets, cursor = [], 0
    for _, original in blocks:
        offsets.append(cursor)
        cursor += len(original)
    changed = [i for i, (_, original) in enumerate(blocks)
               if bytes(image[offsets[i]:offsets[i] + len(original)]) != original]
    patched = bytearray(payload)
    if changed:
        first, last = changed[0], changed[-1]
        while True:
            end = offsets[last] + len(blocks[last][1])
            slots = [part['chunk_size']] * (last - first + 1)
            if last == len(blocks) - 1:
                slots[-1] = start + part['stored_size'] - blocks[last][0]
            packed = _pack(bytes(image[offsets[first]:end]), slots)
            if packed:
                break
            if first == 0 and last == len(blocks) - 1:
                raise ValueError('Edited STAGE2.1 does not fit its stored part')
            first, last = max(0, first - 1), min(len(blocks) - 1, last + 1)
        for (at, _), block, slot in zip(blocks[first:last + 1], packed, slots):
            patched[at:at + slot] = block + bytes(slot - len(block))
    touched = 0 if not changed else last - first + 1
    _, decoded = verify_part(bytes(patched), start, part, decompress=True)
    if decoded != bytes(image):
        raise ValueError('Patched STAGE2.1 does not decode to the edited image')
    return bytes(patched), dict(files=report, reencoded_blocks=touched, total_blocks=len(blocks))
