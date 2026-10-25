#!/usr/bin/env python3
"""Inspect complete, verified Stage2 imagefs catalogs without exporting files.

The catalog profile follows existing MHI2 imagefs tools, with explicit root
and length-prefixed symlink records. Library basename matches show catalog
coverage only; they do not establish runtime linker search order.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import posixpath
import stat
import struct

from identify_stage1_elf_dependencies import inspect_elf
from validate_stage1_unseeded_lzf import scan_elf
from verify_sifs_partitions import verify_archive

SCRIPT_PATHS = ("bin/start_stage3.sh", "bin/gtf2_error_fallback.sh",
                "bin/copy_tmp_core_dumps.sh")


def terminated(data, start, end):
    stop = data.find(b"\0", start, end)
    if stop < 0:
        raise ValueError("Unterminated catalog text")
    raw = data[start:stop]
    if any(c < 32 or c == 127 for c in raw):
        raise ValueError("Control character in catalog text")
    return raw.decode("utf-8")


def parse_catalog(data):
    if len(data) < 24 or len(data) % 4 or data[:8] != b"imagefs\x04":
        raise ValueError("Unexpected complete imagefs profile")
    size, data_start, directory = struct.unpack_from("<III", data, 8)
    if size != len(data) or not 24 <= directory < data_start <= size - 4:
        raise ValueError("Invalid imagefs extents")
    if sum(word[0] for word in struct.iter_unpack("<I", data)) & 0xffffffff:
        raise ValueError("Imagefs additive checksum mismatch")
    cursor = directory
    entries = []
    seen = set()
    while cursor + 4 <= data_start:
        length, flags = struct.unpack_from("<HH", data, cursor)
        if length == 0:
            if data[cursor:cursor + 4] != bytes(4):
                raise ValueError("Malformed catalog terminator")
            return dict(image_size=size, data_start=data_start, directory_offset=directory,
                        catalog_end=cursor, checksum32=0, entries=entries)
        if length < 28 or length % 4 or cursor + length > data_start or len(entries) >= 10000:
            raise ValueError("Invalid catalog record extent")
        inode, mode = struct.unpack_from("<II", data, cursor + 4)
        kind = stat.S_IFMT(mode)
        row = dict(record_offset=cursor, record_size=length, flags=flags,
                   inode=inode, mode=oct(mode))
        if kind == stat.S_IFREG:
            if length < 36:
                raise ValueError("Short regular-file record")
            offset, size = struct.unpack_from("<II", data, cursor + 24)
            if offset < data_start or offset + size > len(data) - 4:
                raise ValueError("File extent outside imagefs data")
            name = terminated(data, cursor + 32, cursor + length)
            row.update(kind="regular", offset=offset, size=size)
        elif kind == stat.S_IFLNK:
            # QNX image_symlink: target offset from path; target size excludes NUL.
            target_offset, target_size = struct.unpack_from("<HH", data, cursor + 24)
            start = cursor + 28
            target = start + target_offset
            end = target + target_size + 1
            if not target_offset or not target_size or end > cursor + length:
                raise ValueError("Invalid symlink string extents")
            name = terminated(data, start, target)
            value = terminated(data, target, end)
            if (len(name.encode()) + 1 != target_offset or
                    len(value.encode()) != target_size or not value):
                raise ValueError("Symlink length mismatch")
            row.update(kind="symlink", target=value)
        elif kind == stat.S_IFDIR:
            name = terminated(data, cursor + 24, cursor + length)
            row.update(kind="directory")
        else:
            raise ValueError(f"Unsupported catalog record type {kind:#x}")
        if (name.startswith('/') or '..' in name.split('/') or
                (name and posixpath.normpath(name) != name) or
                (not name and kind != stat.S_IFDIR) or name in seen):
            raise ValueError("Unsafe or duplicate catalog path")
        seen.add(name)
        row['path'] = name
        entries.append(row)
        cursor += length
    raise ValueError("Missing bounded catalog terminator")


def inspect_image(data):
    catalog = parse_catalog(data)
    elfs = []
    scripts = []
    for row in catalog['entries']:
        if row['kind'] != 'regular':
            continue
        raw = data[row['offset']:row['offset'] + row['size']]
        if raw.startswith(b'\x7fELF'):
            candidate = next((e for e in scan_elf(raw) if e['at'] == 0), None)
            if candidate is None or not candidate['strict_elf_valid']:
                raise ValueError("Invalid ELF catalog member: " + row['path'])
            elfs.append(dict(path=row['path'], size=len(raw), **inspect_elf(raw, 0)))
        if row['path'] in SCRIPT_PATHS:
            if len(raw) > 16384 or b'\0' in raw:
                raise ValueError("Unexpected startup script profile")
            scripts.append(dict(path=row['path'], size=len(raw),
                                sha256=hashlib.sha256(raw).hexdigest(),
                                text=raw.decode('utf-8')))
    return dict(**catalog, counts=dict(Counter(r['kind'] for r in catalog['entries'])),
                elf_files=elfs, selected_scripts=scripts)


def dependency_coverage(images):
    present = defaultdict(list)
    requested = defaultdict(list)
    for image in images:
        for row in image['inspection']['entries']:
            if row['kind'] in ('regular', 'symlink'):
                present[posixpath.basename(row['path'])].append(
                    dict(image=image['name'], path=row['path'], kind=row['kind']))
        for elf in image['inspection']['elf_files']:
            for name in elf['dynamic_strings']['needed']:
                if name is None:
                    raise ValueError("Unresolved ELF DT_NEEDED string")
                requested[name].append(dict(image=image['name'], path=elf['path']))
    return [dict(name=name, requested_by=refs, catalog_basename_matches=present[name])
            for name, refs in sorted(requested.items())]


def inspect_stage3(archive_path, dependencies):
    """Cross-check only startup text and exact library paths in Stage3 QNX6."""
    import zipfile
    from probe_qnx6_root import Volume, image_from_signinfo
    from inspect_qnx6_startup_text import locate
    paths = ["/bin/stage3.sh", "/bin/startup-common.sh"]
    scripts = []
    with zipfile.ZipFile(archive_path) as archive:
        volume = Volume(image_from_signinfo(archive, "stage3.img"))
    for path in paths:
        node = locate(volume, path)
        if stat.S_IFMT(node['mode']) != stat.S_IFREG or node['size'] > 16384:
            raise ValueError("Unexpected Stage3 startup script profile")
        raw = volume.read(node, 0, node['size'])
        if b'\0' in raw:
            raise ValueError("NUL in Stage3 startup script")
        scripts.append(dict(path=path, size=len(raw),
                            sha256=hashlib.sha256(raw).hexdigest(), text=raw.decode('utf-8')))
    checks = []
    missing = [d['name'] for d in dependencies if not d['catalog_basename_matches']]
    for path in ["/lib/" + name for name in missing] + ["/usr/lib/ldqnx.so.2", "/bin/ksh"]:
        try:
            node = locate(volume, path)
        except ValueError as error:
            checks.append(dict(path=path, found=False, reason=str(error)))
        else:
            checks.append(dict(path=path, found=True, size=node['size'], mode=oct(node['mode'])))
    return dict(selected_scripts=scripts, exact_path_checks=checks,
                caution="Absent exact paths do not exclude other locations or providers in Stage1.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--with-stage3', action='store_true',
                        help='also inspect Stage3 startup scripts and exact library paths')
    args = parser.parse_args()
    report = verify_archive(args.archive, decompress=True, inspect_image=inspect_image)
    report['dependency_coverage'] = dependency_coverage(report['images'])
    if args.with_stage3:
        report['stage3'] = inspect_stage3(args.archive, report['dependency_coverage'])
    report['limitations'].extend([
        'Catalog basename matches do not prove runtime linker resolution.',
        'Startup scripts are file contents, not observed executions.',
        'Only Stage2 catalogs are inventoried; absent libraries may be in Stage1 or Stage3.'])
    output = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    print(output, end='')
    if args.json:
        args.json.write_text(output)


if __name__ == '__main__':
    main()
