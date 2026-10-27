import sys
sys.dont_write_bytecode = True
import sys,json,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();target=b[b.index(b'AR20-BIN'):];rows=[]
for i,(alpha,precision,form) in enumerate(itertools.product(('c.r','c.g','c.b','c.a','a.a','b.a','a.r','b.r'),('lowp','mediump'),('mix(a,b,gearStageBig)','mix(b,a,gearStageBig)'))):
 source=f'precision mediump float;varying {precision} vec3 values;uniform sampler2D Texture_KB_big,Texture_KB_small;uniform float gearStageBig;void main(){{vec4 a=texture2D(Texture_KB_big,values.xy);vec4 b=texture2D(Texture_KB_small,values.xy);vec4 c={form};gl_FragColor=vec4(c.rgb,{alpha})*values.z;}}'
 source=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=1,source_alpha=1,destination_rgb=0x303,destination_alpha=0x303))
 d=CgDriver();r=d.compile(source,'fragment');distance=sum((a^b).bit_count() for a,b in zip(r.code,target))+abs(len(r.code)-len(target))*8
 row=dict(index=i,distance=distance,ok=r.ok,match=r.code==target,source=source,mode=1);rows.append(row);print(i,distance,len(r.code),flush=True)
 (ROOT/'alpha-fragment-results.json').write_text(json.dumps(sorted(rows,key=lambda x:x['distance']),indent=2)+'\n')
 if row['match']:
  (ROOT/'fragment.glsl').write_text(source);(ROOT/'fragment.cgbin').write_bytes(r.binary);break
