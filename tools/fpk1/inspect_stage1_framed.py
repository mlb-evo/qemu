#!/usr/bin/env python3
"""Verify complete primary Stage1 ZV/LZF frames and inspect its QNX boot script.

Read-only, in memory. The CRC32 and both QNX checksums must pass before catalog
or boot-script metadata is reported. No proprietary payload is exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

from inspect_stage1_startup_header import inspect as inspect_header
from inspect_stage2_catalogs import inspect_image, dependency_coverage
from verify_sifs_partitions import verify_archive
from validate_stage1_unseeded_lzf import decode

MAX_OUTPUT = 128 * 1024 * 1024


def decode_frames(source, start, end, limit=MAX_OUTPUT):
    if not 0 <= start < end <= len(source):
        raise ValueError('Invalid ZV stream extent')
    cursor = start
    output = bytearray()
    frames = []
    while cursor < end:
        if cursor + 5 > end or source[cursor:cursor + 2] != b'ZV':
            raise ValueError('Missing or truncated ZV frame')
        kind = source[cursor + 2]
        stored, = struct.unpack_from('>H', source, cursor + 3)
        header = 5
        logical = stored
        if kind == 1:
            if cursor + 7 > end:
                raise ValueError('Truncated compressed ZV header')
            logical, = struct.unpack_from('>H', source, cursor + 5)
            header = 7
        elif kind != 0:
            raise ValueError('Unsupported ZV frame type')
        stop = cursor + header + stored
        if not stored or not logical or stop > end or len(output) + logical > limit:
            raise ValueError('Invalid ZV frame lengths')
        raw = source[cursor + header:stop]
        if kind:
            raw, consumed, error = decode(raw, 0, limit=logical)
            if error or consumed != stored or len(raw) != logical:
                raise ValueError('Invalid independently decoded LZF frame')
        frames.append(dict(encoded_offset=cursor, type=kind, stored_size=stored,
                           logical_size=logical, decoded_offset=len(output)))
        output.extend(raw)
        cursor = stop
        if len(frames) > 4096:
            raise ValueError('Too many ZV frames')
    return bytes(output), frames


def decode_archive(path):
    with zipfile.ZipFile(path) as archive:
        matches = [n for n in archive.namelist() if n.endswith('/stage1_ifs.img')]
        if len(matches) != 1:
            raise ValueError('Expected exactly one primary Stage1')
        raw = archive.read(matches[0])
    if raw[:3] != b'HSP' or len(raw) < 0xc2 + 0x800:
        raise ValueError('Unexpected Stage1 envelope')
    source = raw[0xc2:]
    stored, = struct.unpack_from('<I', source)
    start = 0x7f8
    end = start + stored - 4
    if stored < 4 or end + 4 > len(source):
        raise ValueError('Invalid Stage1 stored extent')
    output, frames = decode_frames(source, start, end)
    expected, = struct.unpack_from('<I', source, end)
    actual = zlib.crc32(output) & 0xffffffff
    if actual != expected:
        raise ValueError('Stage1 decoded CRC32 mismatch')
    return output, dict(source_coordinate_origin=0xc2, stream_offset=start,
                        stream_end=end, raw_member_stream_offset=0xc2 + start,
                        stored_bytes_including_crc32=stored, crc32=hex(actual),
                        decoded_size=len(output), decoded_sha256=hashlib.sha256(output).hexdigest(),
                        frames=frames)


def startup_layout(data):
    if len(data) < 264 or len(data) % 4:
        raise ValueError('Short or unaligned QNX image')
    header = inspect_header(data, 8)
    if (header['signature'] != '0xff7eeb' or header['version_u16'] != 1 or
            header['header_size'] != 256 or header['machine'] != 40 or
            header['preboot_size'] != 8 or header['compression_bits'] != '0x0' or
            header['paddr_bias'] != '0x0'):
        raise ValueError('Unexpected decoded startup header')
    end = 8 + header['startup_size']
    if (not 264 <= end < len(data) or end % 4 or
            8 + header['stored_size'] != len(data) or
            header['startup_size'] + header['imagefs_size'] != header['stored_size']):
        raise ValueError('Inconsistent decoded startup sizes')
    if sum(x[0] for x in struct.iter_unpack('<I', data[8:end])) & 0xffffffff:
        raise ValueError('QNX startup checksum mismatch')
    base = int(header['image_paddr'], 16) - header['preboot_size']
    entry = int(header['startup_vaddr'], 16) - base
    if not 264 <= entry < end - 4 or entry % 4:
        raise ValueError('Startup entry outside decoded startup region')
    return dict(header=header, decoded_imagefs_offset=end, startup_checksum32=0,
                implied_load_address=hex(base), entry_decoded_offset=hex(entry),
                caution='Header-consistent mapping; actual bootloader/CPU handoff remains unverified.')


def boot_strings(record, offset, count):
    values = []
    for _ in range(count):
        end = record.find(b'\0', offset)
        if end < 0:
            raise ValueError('Unterminated boot-script string')
        value = record[offset:end]
        if any(c < 32 or c > 126 for c in value):
            raise ValueError('Non-ASCII boot-script string')
        values.append(value.decode('ascii'))
        offset = end + 1
    if any(record[offset:]):
        raise ValueError('Unexpected boot-script trailing data')
    return values


def parse_boot_script(data):
    cursor = 0
    rows = []
    while cursor + 4 <= len(data):
        size, kind, spare = struct.unpack_from('<HBB', data, cursor)
        if size == 0:
            if any(data[cursor:]):
                raise ValueError('Malformed boot-script terminator')
            return rows
        if size < 4 or size % 4 or cursor + size > len(data) or spare:
            raise ValueError('Invalid boot-script record extent')
        record = data[cursor:cursor + size]
        row = dict(offset=cursor, size=size, type=kind)
        if kind == 0:
            if size < 12:
                raise ValueError('Short external boot command')
            cpu, flags, ext0, ext1, policy, priority, argc, envc = record[4:12]
            strings = boot_strings(record, 12, 1 + argc + envc)
            row.update(kind='external', executable=strings[0], argv=strings[1:1 + argc],
                       env=strings[1 + argc:], cpu=cpu, flags=hex(flags),
                       background=bool(flags & 0x20), policy=policy, priority=priority,
                       extended_scheduler=[ext0, ext1])
        elif kind in (1, 2):
            if size < 8:
                raise ValueError('Short wait/reopen boot command')
            checks, = struct.unpack_from('<H', record, 4)
            path, = boot_strings(record, 6, 1)
            row.update(kind='waitfor' if kind == 1 else 'reopen', path=path,
                       checks=checks, maximum_wait_ms=checks * 100)
        elif kind == 4:
            source, destination = boot_strings(record, 4, 2)
            row.update(kind='procmgr_symlink', source=source, destination=destination)
        else:
            raise ValueError('Unsupported boot-script command type')
        rows.append(row)
        cursor += size
        if len(rows) > 10000:
            raise ValueError('Too many boot-script records')
    raise ValueError('Missing boot-script terminator')


def inspect_archive(path, with_stage2=False):
    decoded, framing = decode_archive(path)
    layout = startup_layout(decoded)
    image = decoded[layout['decoded_imagefs_offset']:]
    inspection = inspect_image(image)
    bootstrap_inodes = [i for i in struct.unpack_from('<4I', image, 20) if i]
    bootstrap_files = []
    for inode in bootstrap_inodes:
        matches = [r['path'] for r in inspection['entries'] if r['inode'] == inode and r['kind'] == 'regular']
        if len(matches) != 1:
            raise ValueError('Ambiguous bootstrap inode')
        bootstrap_files.extend(matches)
    boot_inode, = struct.unpack_from('<I', image, 36)
    boot = [r for r in inspection['entries'] if r['inode'] == boot_inode and r['kind'] == 'regular']
    if len(boot) != 1:
        raise ValueError('Ambiguous startup script inode')
    row = boot[0]
    script = image[row['offset']:row['offset'] + row['size']]
    report = dict(framing=framing, startup=layout,
                  images=[dict(name='STAGE1', inspection=inspection)],
                  imagefs_sha256=hashlib.sha256(image).hexdigest(), bootstrap_files=bootstrap_files,
                  boot_script=dict(path=row['path'], inode=boot_inode,
                                   sha256=hashlib.sha256(script).hexdigest(),
                                   records=parse_boot_script(script)), selected_text=[])
    for row in inspection['entries']:
        if row['path'] in ('bin/mount_nand.sh', 'etc/fstab') and row['kind'] == 'regular':
            text = image[row['offset']:row['offset'] + row['size']]
            if len(text) > 16384 or b'\0' in text:
                raise ValueError('Unexpected Stage1 text profile')
            report['selected_text'].append(dict(path=row['path'], text=text.decode('utf-8')))
    if with_stage2:
        stage2 = verify_archive(path, decompress=True, inspect_image=inspect_image)
        report['images'].extend(stage2['images'])
    report['dependency_coverage'] = dependency_coverage(report['images'])
    report['limitations'] = ['Static boot-script order is not a successful execution trace.',
                             'Library basename coverage does not prove runtime resolution.',
                             'Recovery Stage1 is not decoded by this primary-image profile.']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--with-stage2', action='store_true', help='also check Stage1/Stage2 library coverage (requires lzokay)')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    output = json.dumps(inspect_archive(args.archive, args.with_stage2), indent=2) + '\n'
    print(output, end='')
    if args.json:
        args.json.write_text(output)


if __name__ == '__main__':
    main()
