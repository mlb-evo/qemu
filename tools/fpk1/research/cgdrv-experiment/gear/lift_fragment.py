"""Recognise a decoded RGB texture-mix pipeline; reject other pipelines."""
import sys
sys.dont_write_bytecode = True
import argparse,json,struct
from pathlib import Path
from decode_fragment import decode
from lift_vertex import sections,records

def lift(path):
 b=path.read_bytes();sec=sections(b);names=sec[1][1];name=lambda x:names[x:].split(b'\0')[0].decode()
 ir=decode(b);packets=ir['packets'];assert len(packets)==3,'Need three ALU packets'
 vary=records(sec[4][1],28);assert len(vary)==1 and vary[0][3]==0x8b51,'Need one vec3 varying'
 varying=name(vary[0][0]);uniforms=records(sec[8][1],32)
 samplers={};scalars={}
 for w in records(sec[14][1],8):samplers[(w[0]>>8)&255]=name(w[1])
 for i,w in enumerate(uniforms):
  if w[1]==0x1406:
   binding=struct.unpack_from('<I',sec[13][1],i*8)[0];assert binding&255==5
   scalars[32+(binding>>16)]=name(w[0])
 assert set(samplers)=={0,1} and set(scalars)=={32},'Need two samplers and c0'
 # This is a supported MFU/TEX configuration, not an assumption about arbitrary streams.
 assert ir['arrays']['0x701']==[0,0x430,0x431],'Unsupported texture routing'
 assert ir['arrays']['0x604']==[0x104e51ba,0x00408200,0,0x00408000],'Unsupported MFU routing'
 def operand(reg,half=0,fx10=1,negate=0,minus_one=0):
  return dict(reg=reg,half=half,minus_one=minus_one,fx10=fx10,absolute=0,negate=negate,times_two=0)
 tex0=[operand(6,0),operand(6,1),operand(7,0)];tex1=[operand(10,0),operand(10,1),operand(11,0)]
 for packet in packets:
  for ins in packet:
   assert ins['opcode']==0 and not ins['send'] and not ins['recv'] and not ins['add_disable'] and ins['scale']==0,'Unsupported ALU mode'
 for j in range(3):
  x=packets[0][j];assert x['operands']==[dict(tex0[j],negate=1),operand(32,fx10=0),tex1[j]]
  assert x['d']==dict(enabled=1,selector='B',half=0,minus_one=0,absolute=0,fx10=0) and x['high']==x['low']==1
  x=packets[1][j];assert x['operands']==[tex0[j],operand(5),operand(24+j,fx10=0)]
  assert x['d']==dict(enabled=1,selector='B',half=0,minus_one=0,absolute=0,fx10=1) and x['saturate']==1
 assert packets[0][3]['dst']==packets[1][3]['dst']==31,'Unsupported fourth ALU operation'
 source_channels={};order={(2,0):0,(2,1):1,(3,0):2,(3,1):3}
 for x in packets[2]:
  assert x['operands'][0]==operand(26,negate=1,minus_one=1) and x['d']['enabled']==0,'Unsupported framebuffer blend'
  assert x['high']+x['low']==1 and x['dst'] in (2,3)
  half=x['high'];assert x['operands'][1]==operand(x['dst'],half)
  reg=x['operands'][2]['reg'];assert reg in (24,25,26)
  expected_half=packets[1][reg-24]['high'];assert x['operands'][2]==operand(reg,expected_half)
  source_channels[order[(x['dst'],half)]]='rgb'[reg-24]
 assert source_channels[3]=='b','Alpha must match the source-over factor'
 swizzle=''.join(source_channels[i] for i in range(4))
 source=(f'precision mediump float;varying lowp vec3 {varying};'
         f'uniform sampler2D {samplers[0]},{samplers[1]};uniform highp float {scalars[32]};'
         f'void main(){{vec3 c=clamp(mix(texture2D({samplers[0]},{varying}.xy).rgb,'
         f'texture2D({samplers[1]},{varying}.xy).rgb,{scalars[32]})*{varying}.z,0.0,1.0);'
         f'gl_FragColor=c.{swizzle};}}\n')
 return source,dict(blend=1,swizzle=swizzle,samplers=samplers,uniform=scalars[32],varying=varying)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('binary',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 source,model=lift(a.binary);a.output.write_text(source);a.output.with_suffix('.lift.json').write_text(json.dumps(model,indent=2)+'\n');print(model)
