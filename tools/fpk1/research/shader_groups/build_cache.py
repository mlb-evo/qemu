"""Stage only numerically checked vertices and exact-oracle-checked fragments."""
import sys
sys.dont_write_bytecode=True
import json,re,shutil
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
ART=REPO/'build_fpk1/research-artifacts';OUT=ART/'shader_groups';CACHE=OUT/'cache';CACHE.mkdir(exist_ok=True)
base=ART/'cgdrv-experiment/gear/shader-cache'
for p in base.iterdir():
 if p.suffix in ('.glsl','.blend'):shutil.copy2(p,CACHE/p.name)
accepted=[]
for row in json.loads((OUT/'vertex-checks.json').read_text()):
 if not row['passed']:continue
 key=row['key'];shutil.copy2(OUT/'vertices'/f'{key}.glsl',CACHE/f'{key}.glsl');(CACHE/f'{key}.blend').write_text('0\n');accepted.append(dict(key=key,stage='vertex',validation='raw-instruction CPU versus GPU transform feedback'))
for row in json.loads((OUT/'compiled.json').read_text()):
 if not row['compile_ok'] or not row['code_exact'] or row['unimplemented']:continue
 key=row['key'];source=(OUT/'candidates'/f'{key}.glsl').read_text()
 # GLES requires identical uniform precision across linked stages, while the
 # Tegra compiler packs the same application uniform separately in each stage.
 source=re.sub(r'uniform lowp (float|vec[234]) ',r'uniform highp \1 ',source)
 (CACHE/f'{key}.glsl').write_text(source);(CACHE/f'{key}.blend').write_text('1\n');accepted.append(dict(key=key,stage='fragment',validation='exact original-precision Cg target stream',host_uniform_precision='highp for cross-stage linking'))
(OUT/'cache-manifest.json').write_text(json.dumps(accepted,indent=2)+'\n');print('staged',len(accepted),'validated programs')
