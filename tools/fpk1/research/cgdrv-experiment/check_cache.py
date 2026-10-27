"""Check native glShaderBinary loading and GL compile status for local candidates."""
import sys
sys.dont_write_bytecode = True
import json,struct,subprocess
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
def u(*v):return struct.pack('<'+'I'*len(v),*v)
results=[]
with (ROOT/'cache-glhost.log').open('wb') as log:
 p=subprocess.Popen([str(SCRIPT_ROOT/'glhost-with-cache')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
 def send(op,data=b''):
  p.stdin.write(u(op,len(data))+data);p.stdin.flush()
 def query(op,data):
  send(op,data);b=p.stdout.read(4);assert len(b)==4;return struct.unpack('<i',b)[0]
 send(1,u(32,32))
 for i,row in enumerate(json.loads((ROOT/'recovered.json').read_text()),1):
  b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries'/(row['key']+'.bin')).read_bytes()
  send(7,u(i,0x8b31 if row['stage']=='vertex' else 0x8b30))
  send(110,u(1,0x890b,len(b),i)+b)
  status=query(102,u(i,0x8b81));results.append({'key':row['key'],'compile_status':status})
  print(row['key'],status,flush=True)
 assert query(105,b'')==0
 p.stdin.close();assert p.wait(timeout=10)==0
assert all(r['compile_status']==1 for r in results)
(ROOT/'cache-check.json').write_text(json.dumps(results,indent=2)+'\n')
