"""Link every firmware material pair from the shader audit with the translated sources.

Also flags uniforms whose declarations differ between the two stages, which GLES
rejects at link time. Usage: check_links.py [CACHE_DIR]
"""
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import glrun

REPO = next(p for p in HERE.parents if (p / 'hw/arm/fpk1.c').is_file())
ART = REPO / 'build_fpk1/research-artifacts'


def main():
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else ART / 'shader-translate/cache'
    manifest = json.loads((ART / 'shader-audit/manifest.json').read_text())
    ctx = glrun.Context(4, 4)
    seen, rows = set(), []
    for container in manifest['containers']:
        for pair in container['pairs']:
            keys = tuple(s['key'] for s in pair['stages'])
            if keys in seen:
                continue
            seen.add(keys)
            row = dict(keys=keys, material=pair['material'], resource=container['path'])
            paths = [cache / f'{k}.glsl' for k in keys]
            if not all(p.exists() for p in paths):
                row['error'] = 'not translated'
            else:
                try:
                    ctx.program(paths[0].read_text(), paths[1].read_text())
                    row['linked'] = True
                except RuntimeError as error:
                    row['error'] = str(error)
            rows.append(row)
    (ART / 'shader-translate/links.json').write_text(json.dumps(rows, indent=1) + '\n')
    bad = [r for r in rows if not r.get('linked')]
    print(f'linked {len(rows) - len(bad)}/{len(rows)}')
    for r in bad:
        print(' ', r['material'], r['keys'], r['error'][:300])


if __name__ == '__main__':
    main()
