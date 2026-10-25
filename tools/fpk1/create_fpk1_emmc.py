#!/usr/bin/env python3
"""Assemble a synthetic FPK1 eMMC image from one update archive (diagnostic only).

Layout evidence:
- sifsloader reads STAGE2.2 part 1 from /dev/emmc0 at raw byte 0x200200; that
  is the first LZO block of stage2_nand.img (payload +0x200), so the payload
  (raw member +0xba, ``ESO_BIN``) is placed at byte 0x200000.
- Stage1 etc/fstab mounts emmc0t177.3..7 (QNX type-177 partitions, counted in
  MBR/EBR order): persist_swdl, temp_fpk, persist_fpk (rw), stage3, app (ro).

Unknown and therefore synthetic: the real partition offsets/sizes, the contents
of t177.0..2 (left unformatted) and the writable volumes (empty QNX6 via
tools/mhi2/qnx6_image.py). Output is a sparse raw file; keep it out of Git.
"""
import argparse
import contextlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import zipfile

from verify_qnx6_superblocks import expand
from verify_sifs_partitions import WRAPPER, member, verify_archive

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'mhi2'))
import qnx6_image  # noqa: E402

MIB = 1 << 20
SECTOR = 512
NAND_BASE = 0x200000
DISK_SIZE = 1 << 30


def entry(kind, start, count):
    return struct.pack('<B3sB3sII', 0, b'\xfe\xff\xff', kind, b'\xfe\xff\xff', start, count)


def layout(stage3_bytes, app_bytes, writable_mib=32, spare_mib=1, first_mib=16):
    """Return [(label, start_sector, sectors)] for t177.0 .. t177.7."""
    sizes = [('t177.0', spare_mib * MIB), ('t177.1', spare_mib * MIB), ('t177.2', spare_mib * MIB),
             ('persist_swdl', writable_mib * MIB), ('temp_fpk', writable_mib * MIB),
             ('persist_fpk', writable_mib * MIB), ('stage3', stage3_bytes), ('app', app_bytes)]
    rows, cursor = [], first_mib * MIB // SECTOR
    for index, (label, size) in enumerate(sizes):
        if index >= 3:
            cursor += 2048  # room for the EBR preceding each logical partition
        sectors = -(-size // SECTOR)
        rows.append((label, cursor, sectors))
        cursor += -(-sectors // 2048) * 2048
    if cursor * SECTOR > DISK_SIZE:
        raise ValueError('Partitions exceed the synthetic eMMC size')
    return rows


def write_tables(stream, rows):
    mbr = bytearray(512)
    for i in range(3):
        _, start, count = rows[i]
        mbr[446 + 16 * i:462 + 16 * i] = entry(177, start, count)
    ext = rows[3][1] - 2048
    total = DISK_SIZE // SECTOR
    mbr[446 + 48:462 + 48] = entry(5, ext, total - ext)
    mbr[510:] = b'\x55\xaa'
    stream.seek(0)
    stream.write(mbr)
    logical = rows[3:]
    for i, (_, start, count) in enumerate(logical):
        ebr = bytearray(512)
        ebr[446:462] = entry(177, 2048, count)
        if i + 1 < len(logical):
            following = logical[i + 1][1] - 2048
            ebr[462:478] = entry(5, following - ext, logical[i + 1][2] + 2048)
        ebr[510:] = b'\x55\xaa'
        stream.seek((start - 2048) * SECTOR)
        stream.write(ebr)


def blank_volume(root, target, inode_slack=2047):
    """Empty QNX6 volume (with dumps/) whose image size equals ``target``.

    fs-qnx6 reports errno 302 unless the volume spans its whole partition.
    Free data blocks are grown instead of partition_blocks, which would extend
    the volume past its allocation bitmap.
    """
    source, volume = root / 'blank', root / 'blank.qnx6'
    # copy_tmp_core_dumps.sh waits for /mnt/temp_fpk/dumps/.
    (source / 'dumps').mkdir(parents=True, exist_ok=True)
    qnx6_image.INODE_SLACK = inode_slack
    slack = target // qnx6_image.BS - 512
    for _ in range(8):
        with contextlib.redirect_stdout(sys.stderr):
            size = qnx6_image.build(str(source), str(volume), slack)
        if size == target:
            return volume.read_bytes()
        slack += (target - size) // qnx6_image.BS
    raise ValueError('Could not size the empty QNX6 volume to its partition')


def create(archive, output, writable_mib=32, inode_slack=2047):
    verification = verify_archive(archive)
    with zipfile.ZipFile(archive) as source:
        nand = member(source, 'stage2_nand.img', b'ESO_BIN\0')
        stage3, app = expand(source, 'stage3.img'), expand(source, 'app.img')
    rows = layout(len(stage3), len(app), writable_mib)
    if NAND_BASE + len(nand) > rows[0][1] * SECTOR:
        raise ValueError('stage2_nand payload overlaps the first partition')
    with tempfile.TemporaryDirectory(prefix='fpk1-emmc-') as directory:
        root = Path(directory)
        blank = blank_volume(root, writable_mib * MIB, inode_slack)
        with output.open('xb') as stream:
            stream.truncate(DISK_SIZE)
            write_tables(stream, rows)
            stream.seek(NAND_BASE)
            stream.write(nand)
            for label, start, _ in rows:
                data = {'stage3': stage3, 'app': app}.get(label)
                if label in ('persist_swdl', 'temp_fpk', 'persist_fpk'):
                    data = blank
                if data:
                    stream.seek(start * SECTOR)
                    stream.write(data)
    output.chmod(0o600)
    return dict(output=str(output), size=DISK_SIZE, stage2_nand_offset=hex(NAND_BASE),
                stage2_nand_bytes=len(nand), verified_images=[r['name'] for r in verification['images']],
                partitions=[dict(qnx=f'emmc0t177{"" if i == 0 else "." + str(i)}', label=label,
                                 start_sector=start, sectors=count) for i, (label, start, count) in enumerate(rows)],
                caution='Synthetic layout: partition placement and t177.0..2 contents are not from a device.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--writable-mib', type=int, default=32)
    parser.add_argument('--inode-slack', type=int, default=2047)
    args = parser.parse_args()
    print(json.dumps(create(args.archive, args.output, args.writable_mib,
                            args.inode_slack), indent=2))


if __name__ == '__main__':
    main()
