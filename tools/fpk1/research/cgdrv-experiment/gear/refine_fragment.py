import sys
sys.dont_write_bytecode = True
import sys,json,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';BASE=ROOT.parent;REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
original=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();at=original.index(b'AR20-BIN');target=original[at:]
rows=json.loads((BASE/'gear-fragment-candidates.json').read_text());results=[]
for row in rows:
 if row['index']>=16:continue
 d=CgDriver();r=d.compile(row['source'],'fragment')
 distance=sum((a^b).bit_count() for a,b in zip(r.code,target))+abs(len(r.code)-len(target))*8
 out={'index':row['index'],'distance_bits':distance,'length':len(r.code),'source':row['source']};results.append(out);print(row['index'],distance,flush=True)
 if len(r.code)==len(target):(ROOT/f"candidate-{row['index']}.bin").write_bytes(original[:at]+r.code)
(ROOT/'fragment-ranking.json').write_text(json.dumps(sorted(results,key=lambda x:x['distance_bits']),indent=2)+'\n')
