import sys
sys.dont_write_bytecode = True
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
body=(ROOT/'fragment-lifted.glsl').read_text();source=source_with_profile_blend(body,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=1,source_alpha=1,destination_rgb=0x303,destination_alpha=0x303))
d=CgDriver();r=d.compile(source,'fragment');b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();match=r.code==b[b.index(b'AR20-BIN'):]
report=dict(ok=r.ok,code_match=match,code_bytes=len(r.code),unimplemented=d.unimplemented)
(ROOT/'fragment-lifted-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report);assert r.ok and match and not d.unimplemented
