"""Local ALU lift for bounded single-texture source-over pipelines; fail closed."""
import sys
sys.dont_write_bytecode=True
import json,struct
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
sys.path.insert(0,str(REPO/'tools/fpk1/research/cgdrv-experiment/gear'))
from decode_fragment import decode
from lift_vertex import sections,records,TYPES
class Unsupported(ValueError):pass

def need(condition,reason):
 if not condition:raise Unsupported(reason)
def expr(op,a,b):
 if op=='*':
  if a=='0.0' or b=='0.0':return '0.0'
  if a=='1.0':return b
  if b=='1.0':return a
 if op=='+':
  if a=='0.0':return b
  if b=='0.0':return a
 return f'({a}{op}{b})'
def lift(binary):
 data=binary.read_bytes();sec=sections(data);ir=decode(data);arr=ir['arrays'];packets=ir['packets']
 need(arr['0x701']==[0,0x430] or arr['0x701']==[0,0x430,0],'Single texture routing required')
 need(arr['0x604']==[0x104e51ba,0x00408000],'Unsupported MFU interpolation')
 need(2<=len(packets)<=3,'Need two or three ALU packets')
 names=sec[1][1];name=lambda at:names[at:].split(b'\0')[0].decode()
 varying=records(sec[4][1],28);need(len(varying)==1 and varying[0][3]==0x8b50,'Need one vec2 UV varying')
 varying=name(varying[0][0]);samplers=records(sec[14][1],8)
 need(len(samplers)==1 and (samplers[0][0]>>8)&255==0,'Need sampler s0')
 sampler=name(samplers[0][1]);registers={(6,0):'tex.r',(6,1):'tex.g',(7,0):'tex.b',(7,1):'tex.a'}
 declarations=[f'precision highp float;varying mediump vec2 {varying};uniform sampler2D {sampler};']
 uniforms=[]
 for w in records(sec[8][1],32):
  sym=name(w[0]);typ=w[1]
  if typ==0x8b5e:continue
  need(typ in (0x1406,0x8b50,0x8b51,0x8b52) and w[2]==1,'Unsupported uniform type/array')
  dtype=TYPES[typ]
  loc=struct.unpack_from('<I',sec[13][1],w[3]*4)[0] if w[5] else 0
  precision='lowp' if loc&15==9 else 'highp'
  declarations.append(f'uniform {precision} {dtype} {sym};');uniforms.append(dict(name=sym,type=dtype,precision=precision,active=bool(w[5])))
  if not w[5]:continue
  loc=struct.unpack_from('<I',sec[13][1],w[3]*4)[0];kind=loc&15;reg=32+(loc>>17)
  need(kind in (5,9),'Unsupported uniform register encoding')
  n={0x1406:1,0x8b50:2,0x8b51:3,0x8b52:4}[typ]
  for j in range(n):
   value=sym if n==1 else sym+'.'+'xyzw'[j]
   if kind==5:registers[(reg+j,'fp')]=value
   else:registers[(reg+(((loc>>16)&1)+j)//2,(((loc>>16)&1)+j)%2)]=value
 last=[];body=[f'void main(){{lowp vec4 tex=texture2D({sampler},{varying});']
 def raw(reg,half,fx):
  if reg==31:return str(float(half))
  if 24<=reg<=27:
   need(reg-24<len(last),'Undefined previous ALU result')
   r=last[reg-24];key=half if fx else 'fp';need(key in r,'ALU result precision/half mismatch');return r[key]
  key=(reg,half if fx else 'fp');need(key in registers,'Undefined register '+str(key));return registers[key]
 def operand(o):
  value=raw(o['reg'],o['half'],o['fx10'])
  if o['minus_one']:value=expr('+',value,'-1.0')
  if o['absolute']:value=f'abs({value})'
  if o['negate']:value=f'(-{value})'
  if o['times_two']:value=expr('*',value,'2.0')
  return value
 for packet_index,packet in enumerate(packets[:-1]):
  pending=[];next_results=[]
  for slot,ins in enumerate(packet):
   if ins['raw']=='000fe7e83e41f200':next_results.append({});continue
   need(ins['opcode']==0 and not ins['send'] and not ins['recv'] and ins['dst']<16,'Unsupported ALU operation')
   need((int(ins['raw'],16)>>54)&3==0,'ALU result comparison unsupported')
   a,b,c=ins['operands'];va,vb,vc=operand(a),operand(b),operand(c);d=ins['d']
   if d['enabled']:
    src=b if d['selector']=='B' else c
    vd=raw(src['reg'],d['half'],d['fx10'])
    if d['minus_one']:vd=expr('+',vd,'-1.0')
    if d['absolute']:vd=f'abs({vd})'
   else:vd='1.0'
   ab=expr('*',va,vb);cd=expr('*',vc,vd)
   def temp(value,part):
    scale=(1,2,4,.5)[ins['scale']]
    if scale!=1:value=expr('*',value,str(float(scale)))
    if ins['saturate']:value=f'clamp({value},0.0,1.0)'
    t=f'a{packet_index}_{slot}_{part}';precision='highp' if ins['high'] and ins['low'] and not ins['add_disable'] else 'lowp'
    body.append(f'  {precision} float {t}={value};');return t
   if ins['add_disable']:
    need(ins['high']+ins['low']==1,'Unsupported dual-multiply mask')
    x,y=temp(ab,'a'),temp(cd,'b');result={0:x,1:y} if ins['low'] else {0:y,1:x}
   else:
    value=temp(expr('+',ab,cd),'m')
    result={'fp':value} if ins['high'] and ins['low'] else {1 if ins['high'] else 0:value}
   pending.append((ins['dst'],result));next_results.append(result)
  for dst,result in pending:
   for half,value in result.items():registers[(dst,half)]=value
  last=next_results
 # Factor exactly source + destination*(1-alpha); reject any other framebuffer equation.
 source={};alpha=None
 for ins in packets[-1]:
  need(ins['opcode']==0 and not any(ins[k] for k in ('send','recv','add_disable','scale','saturate')) and not ins['d']['enabled'],'Unsupported framebuffer ALU mode')
  need(ins['dst'] in (2,3) and ins['high']+ins['low']==1,'Unsupported framebuffer output')
  a,b,c=ins['operands'];half=ins['high'];channel=(ins['dst']-2)*2+half
  need(b==dict(reg=ins['dst'],half=half,minus_one=0,fx10=1,absolute=0,negate=0,times_two=0),'Framebuffer destination mismatch')
  need(a['minus_one']==a['negate']==a['fx10']==1 and not a['absolute'] and not a['times_two'],'Source-over factor required')
  coefficient=raw(a['reg'],a['half'],a['fx10']);need(alpha is None or alpha==coefficient,'Varying blend factors');alpha=coefficient
  source[channel]=operand(c)
 need(set(source)=={0,1,2,3} and source[3]==alpha,'Blend factor differs from source alpha')
 body.append('  gl_FragColor=vec4('+','.join(source[i] for i in range(4))+');}')
 return '\n'.join(declarations+body)+'\n',dict(blend=1,varying=varying,sampler=sampler,uniforms=uniforms,ir=ir)
