"""Exercise original binary loading, full link, uniforms, textures and blend pixels."""
import sys
sys.dont_write_bytecode = True
import json,struct,subprocess,itertools
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
def u(*v):return struct.pack('<'+'I'*len(v),*v)
def f(*v):return struct.pack('<'+'f'*len(v),*v)
results=[]
with (ROOT/'pair-glhost.log').open('wb') as log:
 p=subprocess.Popen([str(SCRIPT_ROOT/'glhost-with-gear')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
 def send(op,data=b''):
  p.stdin.write(u(op,len(data))+data);p.stdin.flush()
 def query(op,data):
  send(op,data);b=p.stdout.read(4);assert len(b)==4;return struct.unpack('<i',b)[0]
 def loc(name):return query(101,u(3,len(name))+name.encode())
 def scalar(name,value):
  at=loc(name);assert at>=0,name;send(22,u(at,1)+f(value))
 send(1,u(32,32))
 for sid,key,kind in [(1,'0eca8ca482a50fcc-1840',0x8b31),(2,'15531f8f38610c85-944',0x8b30)]:
  binary=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries'/f'{key}.bin').read_bytes();send(7,u(sid,kind));send(110,u(1,0x890b,len(binary),sid)+binary);assert query(102,u(sid,0x8b81))==1
 send(10,u(3));send(11,u(3,1));send(11,u(3,2))
 for index,name in enumerate(('kzPosition','kzTextureCoordinate0')):send(14,u(3,index,len(name))+name.encode())
 send(12,u(3));assert query(103,u(3,0x8b82))==1;send(13,u(3))
 for name,value in {'gear_charID':3,'gear_char_pos':0,'gear_recc_on_accept':0,'gear_char_width':0,'gear_char_height':0,'gear_atlas_cols':1,'gear_recc_state':1}.items():scalar(name,value)
 send(28,u(loc('kzProjectionCameraWorldMatrix'),1,0)+f(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1))
 big=(160,80,192,32);small=(32,208,64,255);background=(26,51,77,102)
 send(50,u(2,10,11))
 for unit,color,name in [(0,big,'Texture_KB_big'),(1,small,'Texture_KB_small')]:
  send(54,u(0x84c0+unit));send(51,u(0xde1,10+unit));send(53,u(0xde1,0x2801,0x2600));send(53,u(0xde1,0x2800,0x2600));send(52,u(0xde1,0,0x1908,1,1,0,0x1908,0x1401,4)+bytes(color));send(30,u(loc(name),unit))
 send(15,u(1,4));send(16,u(0x8892,4))
 data=f(-1,-1,0,0,0, 1,-1,0,1,0, 1,1,0,1,2, -1,-1,0,0,0, 1,1,0,1,2, -1,1,0,0,2)
 send(17,u(0x8892,len(data),0x88e4)+data)
 for index,size,offset in [(0,3,0),(1,2,12)]:send(19,u(index,size,0x1406,0,20,offset));send(20,u(index))
 send(2,u(0,0,32,32))
 for stage,opacity in itertools.product((-.5,0,.25,.5,1,1.5),(0,.25,.5,1,1.25)):
  scalar('gearStageBig',stage);scalar('LayerRenderOpacity',opacity)
  send(3,f(*(c/255 for c in background)));send(4,u(0x4000));send(31,u(4,0,6));send(120,u(16,16,1,1,0x1908,0x1401));pixel=tuple(p.stdout.read(4))
  c=[min(1,max(0,((1-stage)*a+stage*b)/255*opacity)) for a,b in zip(big[:3],small[:3])]
  src=(c[0],c[1],c[0],c[2]);expected=tuple(round(255*min(1,max(0,s+bg/255*(1-src[3])))) for s,bg in zip(src,background))
  error=max(abs(a-b) for a,b in zip(pixel,expected));results.append(dict(stage=stage,opacity=opacity,pixel=pixel,expected=expected,max_channel_error=error))
  assert error<=3,results[-1]
 assert query(105,b'')==0
 p.stdin.close();assert p.wait(timeout=10)==0
(ROOT/'pair-pixel-check.json').write_text(json.dumps(dict(passed=True,linked=True,cases=len(results),max_channel_error=max(r['max_channel_error'] for r in results),results=results),indent=2)+'\n')
print('linked; 30 pixel cases passed; max error',max(r['max_channel_error'] for r in results))
