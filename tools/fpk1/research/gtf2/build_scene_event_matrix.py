#!/usr/bin/env python3
"""Evidence-gated scene/event catalog: never equate IPC names with scene effects."""
import argparse,csv,struct,sys
from pathlib import Path
BASE=0x100000
# dp, callback (diagnostic string), payload offset, CMP address, handler address
ROWS="""02000225,HMI_EngineID_MKB,0c,574020,584710
0200010b,Config_View_Specifica,0a,5747c8,5796f0
02000178,TelltaleAALA_Display,09,57492c,57d410
02000175,unidentified,02,5749dc,57d280
020001ef,Gear_Display,0a,574ac8,5816ec
020001c2,Config_Driverassist_Media,0f,574b30,58014c
020001e6,ActTest_CommonSoftLEDs,01,574bbc,5812a8
020001ea,ActTest_SoftLEDs,06,574c30,5813ec
020001ec,Gear_Display,09,574c54,581530
020001f6,Gear_Display,03,574cd0,581a64
020001fd,Gear_Display,06,574cfc,582020
02000200,ActTest_CommonSoftLEDs,03,574d20,582200
02000201,ActTest_CommonSoftLEDs,02,574d40,582240
02000216,TelltaleHMI_Blink,02,574da4,582ee0
0200021d,TelltaleHMI_Display,08,574dd0,583ff0
0200021f,TelltaleHMI_Blink,01,574df4,5843d4
02000230,Motor_Hybrid_06,04,574ea0,58490c
02000297,ACC_HMI_Display,08,575360,58644c
02000295,TCH_HMI_EngineRPM,02,5753c0,5863d0
020002ad,CarOutline_HMI,05,57542c,586738
020002c2,ODO_HMI_Distance,08,57549c,58696c
020002cd,TelltaleHMI_Display,04,5754bc,586bf0
020002d2,TelltaleHMI_Display,06,5754ec,586cd0
020002d3,TelltaleHMI_Display,0b,57550c,586d34"""
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('elf',type=Path);p.add_argument('--csv',action='store_true')
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 little endian')
 def w(va):return struct.unpack_from('<I',b,va-BASE)[0]
 result=[]
 for line in ROWS.splitlines():
  dp,name,off,cmp_s,target_s=line.split(',')
  dp=int(dp,16);cmp=int(cmp_s,16);target=int(target_s,16)
  # The event DP literal is loaded one or two instructions before CMP.
  found=False
  for va in (cmp-4,cmp-8):
   ins=w(va)
   if ins&0x0f7f0000!=0x051f0000:continue
   literal=va+8+(ins&4095 if ins&0x800000 else -(ins&4095))
   if BASE<=literal<BASE+len(b)-4 and w(literal)==dp:found=True
  if not found:raise ValueError(f'no matching DP literal at 0x{cmp:x}')
  ins=w(cmp+4);delta=ins&0xffffff
  if delta&0x800000:delta-=0x1000000
  if ins>>24!=0x0a or cmp+12+delta*4!=target:
   raise ValueError(f'bad BEQ 0x{cmp+4:x}')
  family=('configuration' if name.startswith('Config_') else
          'test' if name.startswith('ActTest_') else
          'indicator' if name.startswith(('Telltale','HMI_EngineID')) else
          'vehicle_data')
  result.append(dict(dp_id=f'0x{dp:08x}',callback=name,payload_offset=f'0x{int(off,16):x}',
                     family=family,handler_va=f'0x{target:x}',
                     dispatch_proof='literal+cmp+beq',
                     property_id='unresolved',scene_node='unresolved',
                     binding='unresolved',visual_effect='unresolved',
                     scene_switch='not_proven'))
 if a.csv:
  wr=csv.DictWriter(sys.stdout,fieldnames=list(result[0]));wr.writeheader();wr.writerows(result)
 else:
  for r in result:print(r['dp_id'],r['callback'],r['family'],r['handler_va'])
  print(f"verified {len(result)} DP->HMI routes; {sum(r['callback']!='unidentified' for r in result)} named callbacks")
if __name__=='__main__':main()
