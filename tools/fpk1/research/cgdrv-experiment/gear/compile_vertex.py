import sys
sys.dont_write_bytecode = True
import sys,json,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
s=(ROOT/'vertex.glsl').read_text();d=CgDriver();r=d.compile(s,'vertex');b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/0eca8ca482a50fcc-1840.bin').read_bytes();words=struct.unpack('<'+'I'*(len(b)//4),b);original=b''
for i,w in enumerate(words):
 if w>>28==2 and (w>>16)&0xfff==0x206:
  n=w&65535;original=b[(i+1)*4:(i+1+n)*4];break
out=dict(ok=r.ok,diagnostics=r.diagnostics,code_bytes=len(r.code),original_bytes=len(original),code_match=r.code==original,unimplemented=d.unimplemented,symbols=[])
for i in range(struct.unpack_from('<I',r.binary,12)[0] if r.binary else 0):
 w=struct.unpack_from('<12I',r.binary,48+48*i);out['symbols'].append(dict(name=r.binary[w[4]:].split(b'\0')[0].decode(),datatype=w[0],flags=w[1],location=w[3]))
(ROOT/'vertex-validation.json').write_text(json.dumps(out,indent=2)+'\n');(ROOT/'vertex.cgbin').write_bytes(r.binary);print(json.dumps(out))
assert r.ok and not d.unimplemented
