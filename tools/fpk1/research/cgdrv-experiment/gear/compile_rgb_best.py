import sys
sys.dont_write_bytecode = True
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver
p=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear'
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
s=json.loads((p/'rgb-fragment-results.json').read_text())[0]['source'];r=CgDriver().compile(s,'fragment');(p/'rgb-best.cgbin').write_bytes(r.binary)
b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();at=b.index(b'AR20-BIN');(p/'rgb-best.bin').write_bytes(b[:at]+r.code)
