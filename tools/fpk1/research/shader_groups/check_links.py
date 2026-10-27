"""Link every firmware material pair for which the local/builtin cache has both stages."""
import sys
sys.dont_write_bytecode=True
import json,re,struct,subprocess
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file());ART=REPO/'build_fpk1/research-artifacts';OUT=ART/'shader_groups';SCRIPT=Path(__file__).resolve().parent
manifest=json.loads((ART/'shader-audit/manifest.json').read_text());known=set(re.findall(r'UINT64_C\(0x([0-9a-f]+)\)',(REPO/'tools/mhi2/glforward/host/known_shaders.h').read_text()+(REPO/'tools/mhi2/glforward/host/audi_shaders.h').read_text()))
def u(*v):return struct.pack('<'+'I'*len(v),*v)
results=[];seen=set();sid=0
with (OUT/'pair-links.log').open('wb') as log:
 p=subprocess.Popen([str(SCRIPT/'glhost')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
 def send(op,data=b''):
  p.stdin.write(u(op,len(data))+data);p.stdin.flush()
 def query(op,data):
  send(op,data);return struct.unpack('<i',p.stdout.read(4))[0]
 send(1,u(16,16))
 for container in manifest['containers']:
  for pair in container['pairs']:
   keys=tuple(s['key'] for s in pair['stages'])
   if keys in seen:continue
   if not all((OUT/'cache'/f'{k}.glsl').exists() or k.split('-')[0] in known for k in keys):continue
   seen.add(keys);ids=[];compiled=[]
   for stage,k in zip(pair['stages'],keys):
    sid+=1;ids.append(sid);b=(ART/'shader-audit/binaries'/f'{k}.bin').read_bytes();send(7,u(sid,0x8b31 if stage['stage']=='vertex' else 0x8b30));send(110,u(1,0x890b,len(b),sid)+b);compiled.append(query(102,u(sid,0x8b81)))
   sid+=1;pid=sid;send(10,u(pid));send(11,u(pid,ids[0]));send(11,u(pid,ids[1]));send(12,u(pid));status=query(103,u(pid,0x8b82))
   row=dict(keys=keys,materials=pair['material'],resource=container['path'],compile_status=compiled,linked=status==1);results.append(row)
   print(pair['material'],status,flush=True)
 p.stdin.close();assert p.wait(timeout=10)==0
(OUT/'pair-links.json').write_text(json.dumps(results,indent=2)+'\n');print('linked',sum(r['linked'] for r in results),'/',len(results))
