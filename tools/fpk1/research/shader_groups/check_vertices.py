"""Validate a whole lifted vertex group against raw-instruction numeric execution."""
import sys
sys.dont_write_bytecode=True
import ctypes as C,json,math,random
from pathlib import Path
from gpu_probe import open_probe,OUT,REPO
from vertex_reference import metadata,instructions,run
sys.path.insert(0,str(REPO/'tools/fpk1/research/cgdrv-experiment/gear'))
from lift_vertex import lift
ART=REPO/'build_fpk1/research-artifacts';CAND=OUT/'vertices';CAND.mkdir(exist_ok=True)
lib=open_probe();rng=random.Random(271026);results=[];manifest=json.loads((ART/'shader-audit/manifest.json').read_text())
size=lambda t:16 if t=='mat4' else 1 if t=='float' else int(t[-1])
for key,entry in sorted(manifest['programs'].items(),key=lambda kv:len(kv[1]['uses']),reverse=True):
 if entry['stage']!='vertex':continue
 binary=ART/'shader-audit/binaries'/f'{key}.bin';report=dict(key=key,references=len(entry['uses']),passed=False)
 try:
  source,model=lift(binary);meta=metadata(binary.read_bytes());code=instructions(binary.read_bytes())
  # Uniform/varying interfaces will be harmonized with fragment stages at pairing.
  an=[n.encode() for n,t,i in meta['attributes']];vn=[b'gl_Position']+[n.encode() for n,t,i in meta['varyings']]
  p=lib.probe_build(source.encode(),len(an),(C.c_char_p*len(an))(*an),len(vn),(C.c_char_p*len(vn))(*vn))
  if not p:raise ValueError('GLES compile/link: '+lib.probe_error().decode())
  sizes=[size(t) for n,t,i in meta['attributes']];ni=sum(sizes);no=4+sum(size(t) for n,t,i in meta['varyings']);worst=0;checked=0
  for case in range(5):
   uniforms={}
   for n,t,i in meta['uniforms']:
    if t=='mat4':
     values=[0.0]*16
     for j in range(4):values[j*5]=.5+rng.random()
     values[15]=1.;values[12:15]=[rng.uniform(-.2,.2) for _ in range(3)]
    else:values=[rng.uniform(.1,.9) for _ in range(size(t))]
    if 'gearStageBig'==n:values=[(0.,1.,.37,0.,1.)[case]]
    if 'gear_charID'==n:values=[14. if case%2 else 3.]
    if 'gear_char_pos'==n:values=[(-.2,.1,0.,.2,-.1)[case]]
    uniforms[n]=values;status=lib.probe_uniform(p,n.encode(),len(values),(C.c_float*len(values))(*values))
    if status<0:raise ValueError('Uniform upload failed: '+n)
   inputs=[];references=[]
   for vertex in range(32):
    attrs={n:[rng.uniform(-.8,.8) for _ in range(size(t))] for n,t,i in meta['attributes']}
    if any('color' in n.lower() for n in attrs):
     for n in attrs:
      if 'color' in n.lower():attrs[n]=[rng.random() for _ in attrs[n]]
    for n,t,i in meta['attributes']:inputs.extend(attrs[n])
    references.extend(run(code,meta,attrs,uniforms))
   out=(C.c_float*(32*no))();success=lib.probe_run(p,32,len(sizes),(C.c_int*len(sizes))(*sizes),ni,(C.c_float*len(inputs))(*inputs),no,out)
   if not success:raise ValueError('Transform feedback failed')
   for a,b in zip(out,references):
    if not math.isfinite(a) or not math.isfinite(b):raise ValueError('Nonfinite result')
    err=abs(a-b);worst=max(worst,err)
    if err>2e-4*max(1,abs(b)):raise ValueError(f'Numeric mismatch {a} versus {b} (error {err})')
   checked+=32
  lib.probe_delete(p);report.update(passed=True,vertices=checked,max_abs_error=worst)
  (CAND/f'{key}.glsl').write_text(source);(CAND/f'{key}.ir.json').write_text(json.dumps(model,indent=2)+'\n')
 except (ValueError,KeyError,AssertionError,IndexError,ZeroDivisionError) as e:report['reason']=str(e)
 results.append(report);(OUT/'vertex-checks.json').write_text(json.dumps(results,indent=2)+'\n')
 print(key,report['passed'],report.get('reason',''),flush=True)
print('passed',sum(r['passed'] for r in results),'of',len(results),flush=True)
