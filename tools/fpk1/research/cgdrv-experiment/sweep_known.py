"""Local compiler-oracle experiment, no renderer or firmware changes."""
import sys
sys.dont_write_bytecode = True
import hashlib,json,re,struct,time
from pathlib import Path
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment'
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
OUT=ROOT/'sweep';OUT.mkdir(exist_ok=True)
def stream(binary,stage):
 if stage=='fragment':
  at=binary.find(b'AR20-BIN');return binary[at:] if at>=0 else b''
 w=struct.unpack('<'+'I'*(len(binary)//4),binary)
 for i,v in enumerate(w):
  if v>>28==2 and (v>>16)&0xfff==0x206:
   n=v&0xffff
   if i+1+n<=len(w):return struct.pack('<'+'I'*n,*w[i+1:i+1+n])
 return b''
manifest=json.loads((REPO/'build_fpk1/research-artifacts/shader-audit/manifest.json').read_text())
unknown=set(re.findall(r'UNSUPPORTED NVIDIA shader hash=([0-9a-f]+)',(REPO/'build_fpk1/runs/20261026-195334/glhost.log').read_text()))
binaries={}
for folder in (ROOT/'captures',REPO/'build_fpk1/research-artifacts/shader-audit/binaries'):
 for p in folder.glob('*.bin'):
  b=p.read_bytes();stage='fragment' if b'AR20-BIN' in b else 'vertex';code=stream(b,stage)
  if code:binaries[p.stem]=(stage,code)
results=[]
header=(REPO/'tools/mhi2/glforward/host/audi_shaders.h').read_text()
rows=list(re.finditer(r'UINT64_C\(0x([0-9a-f]+)\),\s*(\d+),\s*"((?:[^"\\]|\\.)*)",\s*(\d+)',header))
for m in rows:
 hash,size,quoted,mode=m.groups();key=f'{hash}-{size}';source=json.loads('"'+quoted+'"');stage='vertex' if 'gl_Position' in source else 'fragment'
 mode=int(mode)
 blends={1:(1,0x303,1,0x303),2:(1,0x303,0,1),3:(0x302,0x303,0x302,0x303),4:(1,0,1,0),5:(0,0,0,0)}
 if mode:
  sr,dr,sa,da=blends[mode];source=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=sr,destination_rgb=dr,source_alpha=sa,destination_alpha=da))
 r={'key':key,'stage':stage,'blend_mode':mode};start=time.monotonic()
 try:
  driver=CgDriver();compiled=driver.compile(source,stage)
  r.update(ok=compiled.ok,code_bytes=len(compiled.code),instructions=compiled.instructions,diagnostics=compiled.diagnostics,unimplemented=sorted(set(driver.unimplemented)))
  r['same_binary_code']=key in binaries and bool(compiled.code) and compiled.code==binaries[key][1]
  r['matching_programs']=[k for k,(s,b) in binaries.items() if compiled.code and s==stage and b==compiled.code]
  r['matching_unsupported']=[k for k in r['matching_programs'] if k.split('-')[0] in unknown]
  if compiled.binary:(OUT/f'{key}.cgbin').write_bytes(compiled.binary)
  (OUT/f'{key}.glsl').write_text(source)
 except Exception as e:r.update(exception=type(e).__name__,detail=str(e))
 r['seconds']=round(time.monotonic()-start,3);results.append(r)
 (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(key,'ok',r.get('ok'),'same',r.get('same_binary_code'),'unsupported',r.get('matching_unsupported'),r.get('exception',''),flush=True)
summary={'compiled':sum(r.get('ok',False) for r in results),'attempted':len(results),'known_comparable':sum(r['key'] in binaries for r in results),'known_code_exact':sum(r.get('same_binary_code',False) for r in results),'unsupported_code_matches':sorted({k for r in results for k in r.get('matching_unsupported',[])})}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
