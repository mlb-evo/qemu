"""Decode all four operands of the supported Tegra ALU packets, local research."""
import sys
sys.dont_write_bytecode = True
import json,struct
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent;ROOT=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/cgdrv-experiment/gear';REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
def decode(binary):
 at=binary.index(b'AR20-BIN')+16;w=list(struct.unpack('<'+'I'*((len(binary)-at)//4),binary[at:]));regs={};arrays={0x541:[],0x601:[],0x604:[],0x701:[],0x801:[],0x804:[],0x901:[]}
 counters={0x541:0x540,0x601:0x600,0x604:0x603,0x701:0x700,0x801:0x800,0x804:0x803,0x901:0x900}
 def store(m,v):
  if m in arrays:
   arr=arrays[m];idx=regs.get(counters[m],0)
   while len(arr)<=idx:arr.append(0)
   arr[idx]=v;regs[counters[m]]=idx+1
  else:regs[m]=v
 i=0
 while i<len(w):
  cmd=w[i];i+=1;op=cmd>>28;method=(cmd>>16)&0xfff;count=cmd&0xffff
  if op in (1,2):
   for j in range(count):store(method+(j if op==1 else 0),w[i+j])
   i+=count
  elif op==4:store(method,count)
  else:raise ValueError(hex(cmd))
 packets=[]
 for sched in arrays[0x801]:
  off,n=sched>>2,sched&3
  for j in range(n):
   packet=[]
   for k in range(4):
    a,b=arrays[0x804][(off+j)*8+2*k:(off+j)*8+2*k+2];ins=(a<<32)|b
    operands=[]
    for shift in (32,19,6):
     v=(ins>>shift)&8191;operands.append(dict(reg=v>>6,half=(v>>5)&1,minus_one=(v>>4)&1,fx10=(v>>3)&1,absolute=(v>>2)&1,negate=(v>>1)&1,times_two=v&1))
    d=ins&63
    packet.append(dict(raw=f'{ins:016x}',opcode=ins>>62,send=(ins>>61)&1,recv=(ins>>60)&1,add_disable=(ins>>59)&1,scale=(ins>>57)&3,saturate=(ins>>56)&1,dst=(ins>>47)&127,high=(ins>>46)&1,low=(ins>>45)&1,operands=operands,d=dict(enabled=(d>>2)&1,selector='C' if d&32 else 'B',half=(d>>4)&1,minus_one=(d>>3)&1,absolute=(d>>1)&1,fx10=d&1)))
   packets.append(packet)
 return dict(packets=packets,arrays={hex(k):v for k,v in arrays.items()})
if __name__=='__main__':
 b=(REPO/'build_fpk1/research-artifacts/shader-audit/binaries/15531f8f38610c85-944.bin').read_bytes();r=decode(b);(ROOT/'fragment-decoded.json').write_text(json.dumps(r,indent=2)+'\n')
 for i,p in enumerate(r['packets']):
  print('PACKET',i)
  for x in p:print('dst',x['dst'],x['high'],x['low'],'A B C',x['operands'],'D',x['d'],'adddisable',x['add_disable'])
