"""Copy the NVIDIA shader binaries a glhost run dumped into /tmp, keyed by hash-size.

Usage: collect.py RUN_DIR [OUT_DIR]. RUN_DIR/glhost.log names each dump; the dumps
are overwritten by the next run, so collect right after the run.
"""
import sys
sys.dont_write_bytecode = True
import json, re
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
    lines = (run/'glhost.log').read_text(errors='replace').splitlines()
    rows = {}
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
