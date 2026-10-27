import sys
sys.dont_write_bytecode = True
import sys,json,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();at=b.index(b'AR20-BIN');rows=[]
for precision in ('lowp','mediump'):
 for form in ('mix(texture2D(Texture_KB_big,values.xy).rgb,texture2D(Texture_KB_small,values.xy).rgb,gearStageBig)*values.z','mix(texture2D(Texture_KB_small,values.xy).rgb,texture2D(Texture_KB_big,values.xy).rgb,gearStageBig)*values.z'):
  body=f'precision mediump float;varying {precision} vec3 values;uniform sampler2D Texture_KB_big,Texture_KB_small;uniform float gearStageBig;void main(){{vec3 c={form};gl_FragColor=vec4(c.r,c.g,c.r,c.b);}}'
  source=source_with_profile_blend(body,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=1,source_alpha=1,destination_rgb=0x303,destination_alpha=0x303))
  d=CgDriver();r=d.compile(source,'fragment');match=r.code==b[at:];print(precision,match,len(r.code),flush=True)
  symbols=[]
  for i in range(struct.unpack_from('<I',r.binary,12)[0]):
   w=struct.unpack_from('<12I',r.binary,48+48*i);symbols.append(dict(name=r.binary[w[4]:].split(b'\0')[0].decode(),datatype=w[0],flags=w[1],location=w[3]))
  binding_ok=all(any(s['name']==n and s['flags']&31==slot for s in symbols) for n,slot in [('Texture_KB_big',0),('Texture_KB_small',1)])
  rows.append(dict(source=source,body=body,code_match=match,samplers_match=binding_ok,symbols=symbols,unimplemented=d.unimplemented))
  if match and binding_ok:
   (ROOT/'fragment.glsl').write_text(body+'\n');(ROOT/'fragment.cgbin').write_bytes(r.binary)
   break
 if rows[-1]['code_match'] and rows[-1]['samplers_match']:break
(ROOT/'fragment-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
assert rows[-1]['code_match'] and rows[-1]['samplers_match']
