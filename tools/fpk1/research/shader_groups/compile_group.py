"""Compile lifted family candidates using the supplied CgDrv oracle."""
import sys
sys.dont_write_bytecode=True
import json,re
from pathlib import Path
from lift_textured import lift
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
ART=REPO/'build_fpk1/research-artifacts';OUT=ART/'shader_groups';CAND=OUT/'candidates';CAND.mkdir(exist_ok=True)
sys.path.insert(0,str(REPO/'tools/fpk1/research/cgdrv-experiment'))
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
inventory=json.loads((OUT/'inventory.json').read_text());results=[]
for group in inventory['fragment_groups'][:3]:
 for row in group['programs']:
  key=row['key'];path=ART/'shader-audit/binaries'/f'{key}.bin'
  try:source,model=lift(path)
  except (ValueError,AssertionError,KeyError,IndexError):continue
  src=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=1,source_alpha=1,destination_rgb=0x303,destination_alpha=0x303))
  d=CgDriver();r=d.compile(src,'fragment');binary=path.read_bytes();original=binary[binary.index(b'AR20-BIN'):]
  entry=dict(key=key,compile_ok=r.ok,code_exact=r.code==original,code_bytes=len(r.code),original_bytes=len(original),unimplemented=d.unimplemented,diagnostics=r.diagnostics,model=model)
  results.append(entry);(CAND/f'{key}.glsl').write_text(source);(CAND/f'{key}.cgbin').write_bytes(r.binary)
  (OUT/'compiled.json').write_text(json.dumps(results,indent=2)+'\n');print(key,r.ok,entry['code_exact'],len(r.code),len(original),flush=True)
