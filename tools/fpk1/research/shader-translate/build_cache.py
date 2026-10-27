"""Translate every known FPK1 shader binary into the glhost cache.

Sources: the KZB programs extracted by shader-audit/audit_sources.py and any binaries
collected from glhost runs with collect.py. Output goes to
build_fpk1/research-artifacts/shader-translate/cache, which build_fpk1/run.sh sets as
MHI2_SHADER_CACHE. Pass --archive ZIP to extract directly from firmware first;
--build-dir selects the build directory (default: build_fpk1).
"""
import sys
sys.dont_write_bytecode = True
import argparse
import subprocess
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ar20 import Unsupported, is_fragment
from translate import fnv, translate

REPO = next(p for p in HERE.parents if (p / 'hw/arm/fpk1.c').is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path,
                        help='extract KZB shaders from this firmware ZIP first')
    parser.add_argument('--build-dir', type=Path, default=REPO / 'build_fpk1')
    args = parser.parse_args()
    artifacts = args.build_dir.resolve() / 'research-artifacts'
    if args.archive:
        subprocess.run([sys.executable, str(HERE.parent / 'shader-audit/audit_sources.py'),
                        '--archive', str(args.archive.resolve()),
                        '--artifacts', str(artifacts)], check=True)
    out = artifacts / 'shader-translate/cache'
    out.mkdir(parents=True, exist_ok=True)
    binaries = {}
    for directory in (artifacts / 'shader-audit/binaries', artifacts / 'shader-translate/binaries'):
        if args.archive and directory == artifacts / 'shader-audit/binaries':
            manifest = json.loads((directory.parent / 'manifest.json').read_text())
            paths = [directory / f'{key}.bin' for key in sorted(manifest['programs'])]
        else:
            paths = sorted(directory.glob('*.bin')) if directory.is_dir() else ()
        for path in paths:
            data = path.read_bytes()
            binaries[f'{fnv(data):016x}-{len(data)}'] = data
    if not binaries:
        parser.error('no shader binaries found; pass --archive to extract firmware shaders')
    report = []
    for key, data in sorted(binaries.items()):
        row = dict(key=key, stage='fragment' if is_fragment(data) else 'vertex')
        try:
            source, blend, warnings = translate(data)
        except Unsupported as error:
            for suffix in ('.glsl', '.blend'):
                (out / f'{key}{suffix}').unlink(missing_ok=True)
            row.update(ok=False, error=f'{type(error).__name__}: {error}')
        else:
            (out / f'{key}.glsl').write_text(source)
            (out / f'{key}.blend').write_text(f'{blend}\n')
            row.update(ok=True, blend=blend, warnings=warnings)
        report.append(row)
    (artifacts / 'shader-translate/report.json').write_text(json.dumps(report, indent=1) + '\n')
    failed = [r for r in report if not r['ok']]
    print(f'translated {len(report) - len(failed)}/{len(report)} into {out}')
    for r in failed:
        print(' ', r['key'], r['stage'], r['error'])
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
