"""Translate every known FPK1 shader binary into the glhost cache.

Sources: the KZB programs extracted by shader-audit/audit_sources.py and any binaries
collected from glhost runs with collect.py. Output goes to
build_fpk1/research-artifacts/shader-translate/cache, which build_fpk1/run.sh sets as
MHI2_SHADER_CACHE.
"""
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ar20 import Unsupported, is_fragment
from translate import fnv, translate

REPO = next(p for p in HERE.parents if (p / 'hw/arm/fpk1.c').is_file())
ART = REPO / 'build_fpk1/research-artifacts'


def main():
    out = ART / 'shader-translate/cache'
    out.mkdir(parents=True, exist_ok=True)
    binaries = {}
    for directory in (ART / 'shader-audit/binaries', ART / 'shader-translate/binaries'):
        for path in sorted(directory.glob('*.bin')) if directory.is_dir() else ():
            data = path.read_bytes()
            binaries[f'{fnv(data):016x}-{len(data)}'] = data
    report = []
    for key, data in sorted(binaries.items()):
        row = dict(key=key, stage='fragment' if is_fragment(data) else 'vertex')
        try:
            source, blend, warnings = translate(data)
        except Unsupported as error:
            row.update(ok=False, error=f'{type(error).__name__}: {error}')
        else:
            (out / f'{key}.glsl').write_text(source)
            (out / f'{key}.blend').write_text(f'{blend}\n')
            row.update(ok=True, blend=blend, warnings=warnings)
        report.append(row)
    (ART / 'shader-translate/report.json').write_text(json.dumps(report, indent=1) + '\n')
    failed = [r for r in report if not r['ok']]
    print(f'translated {len(report) - len(failed)}/{len(report)} into {out}')
    for r in failed:
        print(' ', r['key'], r['stage'], r['error'])
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
