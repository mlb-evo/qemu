"""Validate and stage six source candidates; local debugging only."""
import sys
sys.dont_write_bytecode = True
import hashlib,json,re,shutil,struct
from pathlib import Path
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
CACHE=ROOT/'shader-cache';CACHE.mkdir(exist_ok=True)
for p in (REPO/'tools/fpk1/gl_shaders').iterdir():
 if p.suffix in ('.glsl','.blend'):shutil.copy2(p,CACHE/p.name)
vertex=(ROOT/'sweep/74d4458b49cd7903-620.glsl').read_text()
fragment='precision mediump float;varying mediump vec2 vTexCoord;uniform float BlendIntensity;uniform sampler2D Texture;void main(){gl_FragColor=texture2D(Texture,vTexCoord)*BlendIntensity;}'
candidates={
 'b2d66a7ef7e92483-620':('vertex',vertex,0),
 'c523d814f8442e3c-624':('vertex',vertex.replace('vTexCoord','uv_texture'),0),
 '8b03e2ccf05d18f7-816':('fragment',fragment,1),
 '7e16675cc841e39d-872':('fragment',fragment.replace('void main','uniform float google_barSlider;void main'),1),
 'd46a9126f1554feb-884':('fragment','precision mediump float;varying mediump vec2 vTexCoord;uniform float BlendIntensity,LayerRenderOpacity;uniform sampler2D LayerRenderTexture;void main(){gl_FragColor=texture2D(LayerRenderTexture,vTexCoord)*LayerRenderOpacity;}',1),
 '1a5f619fd0029491-596':('fragment','precision mediump float;void main(){gl_FragColor=vec4(1.0);}',4),
}
report=[]
for key,(stage,source,mode) in candidates.items():
 candidate=source
 if mode:
  dst=0 if mode==4 else 0x303
  candidate=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=1,source_alpha=1,destination_rgb=dst,destination_alpha=dst))
 d=CgDriver();r=d.compile(candidate,stage)
 original=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries'/f'{key}.bin').read_bytes()
 if stage=='fragment':code=original[original.index(b'AR20-BIN'):]
 else:
  words=struct.unpack('<'+'I'*(len(original)//4),original);code=b''
  for i,v in enumerate(words):
   if v>>28==2 and (v>>16)&0xfff==0x206:
    n=v&0xffff;code=original[(i+1)*4:(i+1+n)*4];break
 # Ensure each declared name exists in the shipped reflection string table.
 names=[]
 for match in re.finditer(r'(?:attribute|varying|uniform)\s+(?:(?:lowp|mediump|highp)\s+)?\w+\s+([^;]+);',source):
  names.extend(n.strip() for n in match.group(1).split(','))
 reflection_names_present=all(n.encode()+b'\0' in original for n in names)
 ok=r.ok and r.code==code and reflection_names_present and not d.unimplemented
 row={'key':key,'stage':stage,'blend':mode,'compile_ok':r.ok,'code_match':r.code==code,'reflection_names_present':reflection_names_present,'unimplemented':sorted(set(d.unimplemented)),'accepted':ok,'source':source,'code_sha256':hashlib.sha256(code).hexdigest()}
 report.append(row);print(key,ok,flush=True)
 if ok:
  (CACHE/f'{key}.glsl').write_text(source+'\n');(CACHE/f'{key}.blend').write_text(str(mode)+'\n')
(ROOT/'recovered.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(r['accepted'] for r in report)
