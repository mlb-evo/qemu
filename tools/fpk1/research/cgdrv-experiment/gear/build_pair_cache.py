"""Build the local cache from decoded original binaries, selecting a material by name."""
import sys
sys.dont_write_bytecode = True
import argparse,hashlib,json,shutil
from pathlib import Path
from lift_vertex import lift as lift_vertex
from lift_fragment import lift as lift_fragment
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
p=argparse.ArgumentParser();p.add_argument('--material',default='gear_m_Arrow');a=p.parse_args()
manifest=json.loads((REPO/'build_fpk1/research-artifacts/shader-audit/manifest.json').read_text())
pairs=[(r['path'],pair) for r in manifest['containers'] for pair in r['pairs'] if a.material in pair['material']]
assert len(pairs)==1,'Expected a unique material resource'
resource,pair=pairs[0];cache=ROOT/'shader-cache';cache.mkdir(exist_ok=True)
for f in (ROOT.parent/'shader-cache').iterdir():
 if f.suffix in ('.glsl','.blend'):shutil.copy2(f,cache/f.name)
report=dict(material=a.material,resource=resource,stages=[])
for stage in pair['stages']:
 key=stage['key'];binary=REPO/'build_fpk1/research-artifacts/shader-audit/binaries'/f'{key}.bin'
 source,ir=(lift_vertex if stage['stage']=='vertex' else lift_fragment)(binary)
 mode=0 if stage['stage']=='vertex' else ir['blend'];target=cache/f'{key}.glsl';target.write_text(source);(cache/f'{key}.blend').write_text(str(mode)+'\n')
 report['stages'].append(dict(key=key,stage=stage['stage'],binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(source.encode()).hexdigest(),blend=mode))
(ROOT/'pair-cache-manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
