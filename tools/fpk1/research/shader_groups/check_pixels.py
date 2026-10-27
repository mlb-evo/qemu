"""Fragment family pixels versus a separate numeric execution of original ALU words."""
import sys
sys.dont_write_bytecode=True
import json,random,struct,subprocess
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file());ART=REPO/'build_fpk1/research-artifacts';OUT=ART/'shader_groups';SCRIPT=Path(__file__).resolve().parent
sys.path.insert(0,str(REPO/'tools/fpk1/research/cgdrv-experiment/gear'))
from lift_vertex import sections,records
from decode_fragment import decode

def reference(binary,texture,params,bg):
 sec=sections(binary);ir=decode(binary);names=sec[1][1];regs={(6,0):texture[0],(6,1):texture[1],(7,0):texture[2],(7,1):texture[3],(2,0):bg[0],(2,1):bg[1],(3,0):bg[2],(3,1):bg[3]};last=[]
 for w in records(sec[8][1],32):
  if w[1]==0x8b5e or not w[5]:continue
  name=names[w[0]:].split(b'\0')[0].decode();binding=struct.unpack_from('<I',sec[13][1],w[3]*4)[0];reg=32+(binding>>17)
  values=params[name] if isinstance(params[name],list) else [params[name]]
  for j,value in enumerate(values):
   if binding&15==9:regs[(reg+(((binding>>16)&1)+j)//2,(((binding>>16)&1)+j)%2)]=value
   else:regs[(reg+j,'fp')]=value
 def raw(reg,half,fx):
  if reg==31:return float(half)
  return last[reg-24][half if fx else 'fp'] if 24<=reg<=27 else regs[(reg,half if fx else 'fp')]
 for packet in ir['packets']:
  pending=[];results=[]
  for ins in packet:
   bits=int(ins['raw'],16)
   if ins['raw']=='000fe7e83e41f200':results.append({});continue
   source=[]
   for shift in (32,19,6):
    value=(bits>>shift)&8191;r=value>>6;half=(value>>5)&1;fx=(value>>3)&1
    x=raw(r,half,fx)
    if value&16:x-=1
    if value&4:x=abs(x)
    if value&2:x=-x
    if value&1:x*=2
    source.append(x)
   d=bits&63
   if d&4:
    packed=(bits>>(6 if d&32 else 19))&8191;x=raw(packed>>6,(d>>4)&1,d&1)
    if d&8:x-=1
    if d&2:x=abs(x)
   else:x=1.
   ab=source[0]*source[1];cd=source[2]*x
   def adjust(x):
    x*=(1,2,4,.5)[(bits>>57)&3]
    return min(1,max(0,x)) if bits&(1<<56) else x
   hi=(bits>>46)&1;lo=(bits>>45)&1
   if bits&(1<<59):r={0:adjust(ab),1:adjust(cd)} if lo else {0:adjust(cd),1:adjust(ab)}
   else:
    x=adjust(ab+cd);r={'fp':x} if hi and lo else {1 if hi else 0:x}
   results.append(r);pending.append(((bits>>47)&127,r))
  for dst,r in pending:
   for h,v in r.items():regs[(dst,h)]=v
  last=results
 return [regs[(2,0)],regs[(2,1)],regs[(3,0)],regs[(3,1)]]
def u(*v):return struct.pack('<'+'I'*len(v),*v)
def f(*v):return struct.pack('<'+'f'*len(v),*v)
rows=json.loads((OUT/'compiled.json').read_text());rng=random.Random(1027);results=[]
for row in rows:
 if not row['code_exact']:continue
 key=row['key'];model=row['model'];binary=(ART/'shader-audit/binaries'/f'{key}.bin').read_bytes()
 with (OUT/f'pixels-{key}.log').open('wb') as log:
  p=subprocess.Popen([str(SCRIPT/'glhost')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
  def send(op,data=b''):
   p.stdin.write(u(op,len(data))+data);p.stdin.flush()
  def query(op,data):
   send(op,data);return struct.unpack('<i',p.stdout.read(4))[0]
  def loc(name):return query(101,u(3,len(name))+name.encode())
  send(1,u(8,8));send(7,u(1,0x8b31));source=f'attribute vec3 pos;varying mediump vec2 {model["varying"]};void main(){{gl_Position=vec4(pos,1.0);{model["varying"]}=vec2(0.5);}}'.encode();send(8,u(1,len(source))+source);send(9,u(1));assert query(102,u(1,0x8b81))==1
  send(7,u(2,0x8b30));send(110,u(1,0x890b,len(binary),2)+binary);assert query(102,u(2,0x8b81))==1
  send(10,u(3));send(11,u(3,1));send(11,u(3,2));send(14,u(3,0,3)+b'pos');send(12,u(3));assert query(103,u(3,0x8b82))==1;send(13,u(3))
  send(50,u(1,10));send(54,u(0x84c0));send(51,u(0xde1,10));send(53,u(0xde1,0x2801,0x2600));send(53,u(0xde1,0x2800,0x2600));send(30,u(loc(model['sampler']),0))
  send(15,u(1,4));send(16,u(0x8892,4));vertices=f(-1,-1,0,3,-1,0,-1,3,0);send(17,u(0x8892,len(vertices),0x88e4)+vertices);send(19,u(0,3,0x1406,0,12,0));send(20,u(0));send(2,u(0,0,8,8));worst=0
  for case in range(20):
   texture=[rng.randrange(256) for _ in range(4)];bg=[rng.randrange(256) for _ in range(4)];params={}
   for un in model['uniforms']:
    value=(0,.25,.5,1.,1.5)[case%5]
    values=[value] if un['type']=='float' else [value*(.3+.2*j) for j in range(int(un['type'][-1]))]
    params[un['name']]=values if len(values)>1 else value;at=loc(un['name'])
    if at>=0:send({1:22,2:23,3:24,4:25}[len(values)],u(at,1)+f(*values))
   send(52,u(0xde1,0,0x1908,1,1,0,0x1908,0x1401,4)+bytes(texture));send(3,f(*(x/255 for x in bg)));send(4,u(0x4000));send(31,u(4,0,3));send(120,u(4,4,1,1,0x1908,0x1401));actual=list(p.stdout.read(4))
   expected=[round(255*min(1,max(0,x))) for x in reference(binary,[x/255 for x in texture],params,[x/255 for x in bg])]
   error=max(abs(a-b) for a,b in zip(actual,expected));worst=max(worst,error)
   assert error<=3,(key,case,actual,expected)
  assert query(105,b'')==0;p.stdin.close();assert p.wait(timeout=10)==0
 results.append(dict(key=key,passed=True,cases=20,max_channel_error=worst));(OUT/'fragment-pixels.json').write_text(json.dumps(results,indent=2)+'\n');print(key,worst,flush=True)
print('passed',len(results),'programs',sum(r['cases'] for r in results),'pixels')
