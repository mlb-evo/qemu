import sys
sys.dont_write_bytecode = True
import sys,json,itertools,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();target=b[b.index(b'AR20-BIN'):];rows=[]
for i,(precision,flip,alpha,opacity,mode) in enumerate(itertools.product(('lowp','mediump'),(False,True),('values.z','1.0'),(True,False),(1,3))):
 a,b=('Texture_KB_big','Texture_KB_small') if not flip else ('Texture_KB_small','Texture_KB_big')
 rgb=f'mix(texture2D({a},values.xy).rgb,texture2D({b},values.xy).rgb,gearStageBig)'+('*values.z' if opacity else '')
 source=f'precision mediump float;varying {precision} vec3 values;uniform sampler2D Texture_KB_big,Texture_KB_small;uniform float gearStageBig;void main(){{gl_FragColor=vec4({rgb},{alpha});}}'
 factor=1 if mode==1 else 0x302
 source=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=factor,source_alpha=factor,destination_rgb=0x303,destination_alpha=0x303))
 d=CgDriver();r=d.compile(source,'fragment');distance=sum((a^b).bit_count() for a,b in zip(r.code,target))+abs(len(r.code)-len(target))*8
 row=dict(index=i,distance=distance,ok=r.ok,match=r.code==target,source=source,mode=mode);rows.append(row);print(i,distance,len(r.code),flush=True)
 (ROOT/'rgb-fragment-results.json').write_text(json.dumps(sorted(rows,key=lambda x:x['distance']),indent=2)+'\n')
 if row['match']:
  (ROOT/'fragment.glsl').write_text(source);(ROOT/'fragment.cgbin').write_bytes(r.binary);break
