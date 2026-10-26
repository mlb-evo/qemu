#!/usr/bin/env python3
"""Decompress the KSS microcontroller image from an FPK1 update archive.

KSSApplication.bin is HSP-wrapped; its SignInfo gives the payload offset and
sizes. The payload is LZSS: a flag byte covers eight tokens, read from the
most significant bit; 0 is a literal byte, 1 a two-byte back-reference with
length b0 >> 2 and distance ((b0 & 3) << 8) | b1. The decoder must consume the
whole stored payload and produce exactly UNCOMPRESSED-SIZE bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def lzss_decode(data, limit):
    out, i = bytearray(), 0
    while i < len(data):
        flags = data[i]
        i += 1
        for bit in range(7, -1, -1):
            if i >= len(data):
                break
            if flags >> bit & 1:
                if i + 2 > len(data):
                    raise ValueError('Truncated back-reference')
                b0, b1 = data[i], data[i + 1]
                i += 2
                length, distance = b0 >> 2, ((b0 & 3) << 8) | b1
                if not distance or distance > len(out):
                    raise ValueError(f'Invalid back-reference at input {i - 2:#x}')
                for _ in range(length):
                    out.append(out[-distance])
            else:
                out.append(data[i])
                i += 1
            if len(out) > limit:
                raise ValueError('Output exceeds declared size')
    return bytes(out)


def extract(archive, name='KSSApplication.bin'):
    with zipfile.ZipFile(archive) as source:
        member = next(n for n in source.namelist() if n.endswith('/' + name))
        info = ET.fromstring(source.read(member.rsplit('.', 1)[0] + '_SignInfo.xml'))
        raw = source.read(member)
    start = int(info.findtext('START-BYTE-FLASHDATA'))
    stored = int(info.findtext('COMPRESSED-SIZE'))
    size = int(info.findtext('UNCOMPRESSED-SIZE'))
    if raw[:3] != b'HSP' or start + stored > len(raw):
        raise ValueError('Unexpected HSP member profile')
    image = lzss_decode(raw[start:start + stored], size)
    if len(image) != size:
        raise ValueError(f'Decoded {len(image)} bytes, expected {size}')
    # Word 0 is `ldr pc, [pc, #-4]`; word 1 is the reset target it loads.
    return image, dict(member=member, payload_offset=start, stored_size=stored, size=size,
                       sha256=hashlib.sha256(image).hexdigest(),
                       reset_vector_word=hex(int.from_bytes(image[0:4], 'little')),
                       reset_target=hex(int.from_bytes(image[4:8], 'little')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, help='write the decoded image (keep it out of Git)')
    args = parser.parse_args()
    image, report = extract(args.archive)
    if args.output:
        args.output.write_bytes(image)
        args.output.chmod(0o600)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
