"""Copy the NVIDIA shader binaries a glhost run dumped into /tmp, keyed by hash-size.

Usage: collect.py RUN_DIR_OR_CAPTURE [OUT_DIR]. A MHI2_GL_CAPTURE recording
contains the binaries directly. RUN_DIR/glhost.log instead names temporary
dumps, which are overwritten by the next run; collect these right after the run.
"""
import sys
sys.dont_write_bytecode = True
import json, re, struct
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
ART = REPO/'build_fpk1/research-artifacts/shader-translate'


def fnv(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


def main():
    run = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ART/'binaries'
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    if run.is_file():
        with run.open('rb') as recording:
            while header := recording.read(8):
                if len(header) != 8:
                    raise ValueError('truncated graphics record header')
                opcode, length = struct.unpack('<II', header)
                data = recording.read(length)
                if len(data) != length:
                    raise ValueError('truncated graphics record payload')
                if opcode != 110:
                    continue
                count, _, size = struct.unpack_from('<III', data)
                if count != 1:
                    raise ValueError('expected one binary shader per record')
                binary = data[12 + count * 4:]
                if len(binary) != size:
                    raise ValueError('shader binary size mismatch')
                key = f'{fnv(binary):016x}-{size}'
                (out / f'{key}.bin').write_bytes(binary)
                rows.setdefault(key, {'key': key, 'uses': 0})['uses'] += 1
        (out.parent / 'collected.json').write_text(json.dumps(list(rows.values()), indent=1) + '\n')
        print(len(rows), 'unique binaries from recording')
        return
    lines = (run/'glhost.log').read_text(errors='replace').splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'shader binary (\S+) count=1 size=(\d+)', line)
        if not m:
            continue
        path = Path(m.group(1))
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) != int(m.group(2)):
            continue
        key = f'{fnv(data):016x}-{len(data)}'
        unsupported = i + 1 < len(lines) and 'UNSUPPORTED' in lines[i + 1]
        (out/f'{key}.bin').write_bytes(data)
        row = rows.setdefault(key, {'key': key, 'uses': 0, 'unsupported': unsupported})
        row['uses'] += 1
    (out.parent/'collected.json').write_text(json.dumps(sorted(rows.values(), key=lambda r: r['key']), indent=1) + '\n')
    print(len(rows), 'unique binaries,', sum(r['unsupported'] for r in rows.values()), 'unsupported')


if __name__ == '__main__':
    main()
