"""Bounded inverse-compile experiment for one FPK1 fragment binary."""
import sys
sys.dont_write_bytecode = True
import hashlib,itertools,json,struct,time
from pathlib import Path
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();original=b[b.index(b'AR20-BIN'):]
prefix='precision mediump float;varying mediump vec3 values;uniform sampler2D Texture_KB_big,Texture_KB_small;uniform float gearStageBig;'
expressions=[
 'mix(texture2D(Texture_KB_small,values.xy),texture2D(Texture_KB_big,values.xy),gearStageBig)',
 'mix(texture2D(Texture_KB_big,values.xy),texture2D(Texture_KB_small,values.xy),gearStageBig)',
 'texture2D(Texture_KB_big,values.xy)*gearStageBig+texture2D(Texture_KB_small,values.xy)*(1.0-gearStageBig)',
 'texture2D(Texture_KB_small,values.xy)*gearStageBig+texture2D(Texture_KB_big,values.xy)*(1.0-gearStageBig)',
]
alpha=['c.a*=values.z;','c*=values.z;','c.rgb*=values.z;','']
results=[];start=time.monotonic()
for idx,(expression,opacity,mode) in enumerate(itertools.product(expressions,alpha,(1,3))):
 source=prefix+'void main(){vec4 c='+expression+';'+opacity+'gl_FragColor=c;}'
 src_factor=1 if mode==1 else 0x302
 source=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=src_factor,source_alpha=src_factor,destination_rgb=0x303,destination_alpha=0x303))
 driver=CgDriver();r=driver.compile(source,'fragment');row={'index':idx,'ok':r.ok,'code_bytes':len(r.code),'matches':r.code==original,'mode':mode,'source':source,'unimplemented':sorted(set(driver.unimplemented))}
 results.append(row);(ROOT/'gear-fragment-candidates.json').write_text(json.dumps(results,indent=2)+'\n')
 print(idx,r.ok,len(r.code),'MATCH' if row['matches'] else '',flush=True)
 if row['matches']:
  (ROOT/'gear-fragment-matched.glsl').write_text(source);(ROOT/'gear-fragment-matched.cgbin').write_bytes(r.binary);break
print('tried',len(results),'matched',any(r['matches'] for r in results),'seconds',round(time.monotonic()-start,2),flush=True)
