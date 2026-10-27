import sys
sys.dont_write_bytecode = True
import argparse,json,time,struct,hashlib,re
from pathlib import Path
from cgdrv_harness.cgdrv import CgDriver,source_with_profile_blend

SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment'
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
p=argparse.ArgumentParser();p.add_argument('case');args=p.parse_args()
header=(REPO/'tools/mhi2/glforward/host/audi_shaders.h').read_text()
known={m.group(1):{'size':int(m.group(2)),'source':json.loads('"'+m.group(3)+'"'),'blend':int(m.group(4))} for m in re.finditer(r'UINT64_C\(0x([0-9a-f]+)\),\s*(\d+),\s*"((?:[^"\\]|\\.)*)",\s*(\d+)',header)}
cases={
 'simple-fragment':('fragment','precision mediump float; void main(){gl_FragColor=vec4(1.0);}',None),
 'simple-vertex':('vertex','attribute vec3 position; void main(){gl_Position=vec4(position,1.0);}',None),
 'known-white':('fragment',known['a99e58e0fb584f4f']['source'],'a99e58e0fb584f4f-596'),
 'known-textured-vertex':('vertex',known['74d4458b49cd7903']['source'],'74d4458b49cd7903-620'),
 'known-textured-fragment':('fragment',known['5f0c553272bc2ebd']['source'],'5f0c553272bc2ebd-796'),
}
target,source,shipped=cases[args.case]
if args.case=='known-white':
 source=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=1,source_alpha=1,destination_rgb=0,destination_alpha=0))
if args.case=='known-textured-fragment':
 source=source_with_profile_blend(source,dict(equation_rgb=0x8006,equation_alpha=0x8006,source_rgb=0x302,source_alpha=0x302,destination_rgb=0x303,destination_alpha=0x303))
(ROOT/f'{args.case}.glsl').write_text(source)
started=time.monotonic();out={'case':args.case,'target':target,'source':source}
try:
 d=CgDriver();r=d.compile(source,target)
 out.update(ok=r.ok,binary_bytes=len(r.binary),code_bytes=len(r.code),instructions=r.instructions,log=r.log,error=r.error,diagnostics=r.diagnostics,unimplemented=sorted(set(d.unimplemented)),constructors=d.initialisers)
 if r.binary:(ROOT/f'{args.case}.cgbin').write_bytes(r.binary)
 if shipped:
  capture=REPO/'build_fpk1/research-artifacts/shader-audit/binaries'/f'{shipped}.bin'
  if not capture.exists():capture=ROOT/'captures'/f'{shipped}.bin'
  b=capture.read_bytes();stream=b''
  if target=='fragment':
   at=b.find(b'AR20-BIN')
   out['ar20_offset']=at
   if at>=0:stream=b[at:]
  else:
   w=struct.unpack('<'+'I'*(len(b)//4),b)
   for i,v in enumerate(w):
    if v>>28==2 and (v>>16)&0xfff==0x206:
     count=v&0xffff
     if i+1+count<=len(w):stream=struct.pack('<'+'I'*count,*w[i+1:i+1+count]);break
  out.update(shipped=shipped,shipped_stream_bytes=len(stream),code_sha256=hashlib.sha256(r.code).hexdigest(),shipped_stream_sha256=hashlib.sha256(stream).hexdigest(),direct_code_match=bool(r.code) and r.code==stream)
except Exception as e:
 out.update(exception=type(e).__name__,detail=str(e))
out['seconds']=round(time.monotonic()-started,3)
(ROOT/f'{args.case}.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2),flush=True)
