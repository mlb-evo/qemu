"""Independent numeric interpreter of raw vertex instruction bit fields."""
import sys
sys.dont_write_bytecode=True
import math,struct
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
sys.path.insert(0,str(REPO/'tools/fpk1/research/cgdrv-experiment/gear'))
from lift_vertex import sections,records,TYPES
class Undefined(ValueError):pass
def fp(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def instructions(b):
 w=struct.unpack('<'+'I'*(len(b)//4),b)
 for i,v in enumerate(w):
  if v>>28==2 and (v>>16)&4095==0x206:
   code=w[i+1:i+1+(v&65535)];return [sum(code[i+j]<<(32*(3-j)) for j in range(4)) for i in range(0,len(code),4)]
 raise ValueError('No vertex upload')
def metadata(b):
 sec=sections(b);names=sec[1][1];name=lambda at:names[at:].split(b'\0')[0].decode()
 attrs=[(name(w[0]),TYPES[w[1]],w[2]) for w in records(sec[2][1],16)]
 vary=[(name(w[0]),TYPES[w[3]],w[5]) for w in records(sec[3][1],24)]
 uniforms=[]
 for i,w in enumerate(records(sec[8][1],32)):
  reg=struct.unpack_from('<I',sec[13][1],w[3]*4)[0]>>18;uniforms.append((name(w[0]),TYPES[w[1]],reg))
 const=[list(struct.unpack('<4f',struct.pack('<4I',*w))) for w in records(sec[18][1],16)]
 return dict(attributes=attrs,varyings=vary,uniforms=uniforms,constants=const)
def run(code,meta,attrs,uniforms):
 r={};o={};p=[None]*4;c=[x[:] for x in meta['constants']];v={}
 for name,typ,i in meta['attributes']:
  x=attrs[name][:];v[i]=x+[0.]*(3-len(x))+([1.] if len(x)<4 else [])
 for name,typ,i in meta['uniforms']:
  x=uniforms[name]
  while len(c)<i+(4 if typ=='mat4' else 1):c.append([None]*4)
  if typ=='mat4':
   for k in range(4):c[i+k]=x[4*k:4*k+4]
  elif typ=='float':c[i]=x*4
  else:c[i]=x+[None]*(4-len(x))
 for bits in code:
  get=lambda at,n=1:(bits>>at)&((1<<n)-1)
  constant,attribute,vary=get(76,8),get(72,4),get(2,4)
  pred,pneg=get(109),get(107);ps=[get(104,2),get(102,2),get(100,2),get(98,2)]
  def read(which,component):
   cfg=[(55,57,71,117,[69,67,65,63]),(38,40,54,118,[52,50,48,46]),(21,23,37,119,[35,33,31,29])][which]
   typ=get(cfg[0],2);idx=get(cfg[1],6);sw=get(cfg[4][component],2)
   if typ==1:x=r.get(idx,[None]*4)[sw]
   elif typ==2:x=v[attribute][sw]
   elif typ==3:x=c[constant][sw]
   else:raise Undefined('Unknown source type')
   if x is None:raise Undefined('Read before definition')
   if get(cfg[3]):x=abs(x)
   return -x if get(cfg[2]) else x
  pending=[]
  for scalar,maskbits,regat,reglen,opcode in [(False,[16,15,14,13],111,6,get(86,5)),(True,[20,19,18,17],7,5,get(91,5))]:
   reg=get(regat,reglen);mask=[get(x) for x in maskbits]
   for j,enabled in enumerate(mask):
    if not enabled:continue
    if pred:
     pv=p[ps[j]]
     if pv is None:raise Undefined('Undefined predicate')
     if bool(pv)==bool(pneg):continue
    if scalar:
     a=read(2,0)
     if opcode==1:value=a
     elif opcode==2:value=1./a
     else:raise Undefined('Unsupported scalar opcode '+str(opcode))
    else:
     a=read(0,j)
     if opcode==1:value=a
     elif opcode==3:value=a+read(2,j)
     elif opcode==14:value=a-math.floor(a)
     elif opcode==15:value=math.floor(a)
     else:
      b=read(1,j)
      if opcode==2:value=a*b
      elif opcode==4:value=a*b+read(2,j)
      elif opcode==9:value=min(a,b)
      elif opcode==10:value=max(a,b)
      elif opcode==16:value=float(a==b)
      else:raise Undefined('Unsupported vector opcode '+str(opcode))
    if get(122):value=max(0,min(1,value))
    limit=31 if scalar else 63
    target=o.setdefault(vary,[None]*4) if get(126) and reg==limit else p if get(125) and reg==limit else r.setdefault(reg,[None]*4)
    pending.append((target,j,fp(value)))
  for target,j,value in pending:target[j]=value
 result=o[0][:]
 for _,typ,i in meta['varyings']:result+=o[i][:1 if typ=='float' else int(typ[-1])]
 if any(x is None for x in result):raise Undefined('Undefined output')
 return result
