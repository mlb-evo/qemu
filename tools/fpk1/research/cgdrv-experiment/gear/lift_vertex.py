"""Local straight-line Tegra vertex lifter; unsupported instructions are rejected."""
import sys
sys.dont_write_bytecode = True
import argparse,json,re,struct,subprocess
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear'
TYPES={0x1406:'float',0x8b50:'vec2',0x8b51:'vec3',0x8b52:'vec4',0x8b5c:'mat4'}
def sections(b):
 return {kind:(n,b[off*4:off*4+size]) for kind,off,n,size in (struct.unpack_from('<4I',b,20+16*i) for i in range(struct.unpack_from('<I',b,16)[0]))}
def records(data,step):
 return [struct.unpack_from('<'+'I'*(step//4),data,i) for i in range(0,len(data),step)]
def lift(binary):
 b=binary.read_bytes();sec=sections(b);names=sec[1][1]
 name=lambda off:names[off:].split(b'\0')[0].decode()
 attrs=[(name(w[0]),TYPES[w[1]],w[2]) for w in records(sec[2][1],16)]
 vary=[(name(w[0]),TYPES[w[3]],w[5]) for w in records(sec[3][1],24)]
 assert all(re.fullmatch(r'[A-Za-z_]\w*',n) for n,t,i in attrs+vary),'Attribute/varying arrays unsupported'
 assert len({n for n,t,i in vary})==len(vary),'Duplicate varying entries unsupported'
 uniforms=[];bindings=[]
 for i,w in enumerate(records(sec[8][1],32)):
  sym,typ=name(w[0]),TYPES[w[1]]
  assert re.fullmatch(r'[A-Za-z_]\w*',sym),'Uniform array/field syntax unsupported'
  assert w[2]==1,'Arrays not supported yet'
  loc=struct.unpack_from('<I',sec[13][1],i*8)[0]
  reg=loc>>18
  uniforms.append(f'uniform {typ} {sym};')
  if typ=='mat4':bindings.extend((reg+j,f'{sym}[{j}]') for j in range(4))
  else:bindings.append((reg,{'float':f'vec4({sym})','vec2':f'vec4({sym},0.0,0.0)','vec3':f'vec4({sym},0.0)','vec4':sym}[typ]))
 constants=records(sec[18][1],16)
 text=subprocess.check_output([str(ROOT.parent/'tegra_shader_disasm'),str(binary)],text=True)
 blocks=re.split(r'^    [0-9a-f]{32}.*\n',text,flags=re.M)[1:]
 operations=[];body=[];used_regs=set();out_regs={0}|{i for _,_,i in vary}
 def operand(x):
  assert re.fullmatch(r'-?(?:[rcv]\d+)\.[xyzw]{1,4}',x),x
  return x
 for no,block in enumerate(blocks):
  ops=[];unit=None
  for line in block.splitlines():
   if 'vec op' in line:unit='vec';continue
   if 'scalar op' in line:unit='scalar';continue
   m=re.match(r'        (?:(\(!?p0\.[xyzw]{4}\)) )?(\w+) ([rop]\d+)\.([xyzw]+)(?:, (.*))?$',line)
   if not m:
    if line.startswith('        ') and line.strip() not in ('nop',''):
     raise ValueError('Unsupported operation syntax: '+line.strip())
    continue
   pred,op,dst,mask,args=m.groups();args=[operand(x.strip()) for x in (args or '').split(',') if x.strip()]
   if op=='mov':expr=args[0]
   elif op=='add':expr=f'({args[0]}+{args[1]})'
   elif op=='mul':expr=f'({args[0]}*{args[1]})'
   elif op=='mad':expr=f'({args[0]}*{args[1]}+{args[2]})'
   elif op in ('min','max'):expr=f'{op}({args[0]},{args[1]})'
   elif op=='flr':expr=f'floor({args[0]})'
   elif op=='frc':expr=f'fract({args[0]})'
   elif op=='seq':expr=f'vec4(equal({args[0]},{args[1]}))'
   elif op=='rcp':expr=f'(1.0/{args[0]})'
   else:raise ValueError(f'Unsupported opcode {op}')
   expr=f'vec4({expr})'
   temp=f't{no}_{unit}'
   body.append(f'  vec4 {temp}={expr};')
   ops.append(dict(unit=unit,op=op,dst=dst,mask=mask,args=args,predicate=pred,temp=temp))
  if not ops:raise ValueError('Instruction without supported operations: '+block)
  for op in ops:
   dst,mask,temp,pred=op['dst'],op['mask'],op['temp'],op['predicate']
   if pred:
    invert=pred.startswith('(!');predsw=pred.split('.')[1][:-1]
    for ch in mask:
     pc=predsw['xyzw'.index(ch)];condition=f'p0.{pc}'+('==0.0' if invert else '!=0.0')
     body.append(f'  if({condition}) {dst}.{ch}={temp}.{ch};')
   else:body.append(f'  {dst}.{mask}={temp}.{mask};')
   for token in (dst,*op['args']):used_regs.update(re.findall(r'\br\d+\b',token))
  operations.append(ops)
 declarations=['precision highp float;']+[f'attribute {t} {n};' for n,t,_ in attrs]+uniforms+[f'varying {"mediump" if t=="vec2" else "lowp"} {t} {n};' for n,t,_ in vary]
 initial=['void main(){']
 for reg in sorted(used_regs):initial.append(f'  vec4 {reg}=vec4(0.0);')
 initial.append('  vec4 p0=vec4(0.0);')
 for i in sorted(out_regs):initial.append(f'  vec4 o{i}=vec4(0.0);')
 for n,t,i in attrs:
  expr={'float':f'vec4({n},0.0,0.0,1.0)','vec2':f'vec4({n},0.0,1.0)','vec3':f'vec4({n},1.0)','vec4':n}[t]
  initial.append(f'  vec4 v{i}={expr};')
 constant_count=max([len(constants)]+[i+1 for i,_ in bindings]+[int(x)+1 for x in re.findall(r'\bc(\d+)\b',' '.join(body))])
 constants=constants+[(0,0,0,0)]*(constant_count-len(constants))
 for i,w in enumerate(constants):
  values=struct.unpack('<4f',struct.pack('<4I',*w))
  initial.append(f'  vec4 c{i}=vec4('+','.join(repr(float(x)) for x in values)+');')
 for i,expr in bindings:initial.append(f'  c{i}={expr};')
 outputs=['  gl_Position=o0;']
 for n,t,i in vary:outputs.append(f'  {n}=o{i}.'+{'float':'x','vec2':'xy','vec3':'xyz','vec4':'xyzw'}[t]+';')
 return '\n'.join(declarations+initial+body+outputs+['}'])+'\n',dict(attributes=attrs,varyings=vary,bindings=bindings,operations=operations)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('binary',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 source,model=lift(a.binary);a.output.write_text(source);a.output.with_suffix('.ir.json').write_text(json.dumps(model,indent=2)+'\n');print('lifted',len(model['operations']),'instructions')
