#!/usr/bin/env python3
"""Find exact ARM literal references to named scene-node paths in GTF2.

Distinguishes node-name usage from a proved DP->property binding. This tool
does not claim that a string reference is an instantiated or visible node.
"""
import argparse,csv,struct,sys
from pathlib import Path
BASE=0x100000
TARGETS=(
 'MV_ClusterFull.TubeContainer.CenterTube.GearIndicator',
 'MV_ClusterFull.TubeContainer.RevoTube.GearIndicatorPHEV',
 'PV_WarnPopup_CarOutline.GlassPlate.CarOutline',
 'RV_ClusterFull_Additional.HubContentRevoTube.CarOutline',
)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('elf',type=Path)
 p.add_argument('--csv',action='store_true')
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected ELF32 little-endian')
 def word(va):return struct.unpack_from('<I',b,va-BASE)[0]
 targets={}
 for name in TARGETS:
  off=b.find(name.encode()+b'\x00')
  if off<0:raise ValueError(f'missing scene path: {name}')
  targets[BASE+off]=name
 pointer_slots={}
 for off in range(0,len(b)-3,4):
  val=struct.unpack_from('<I',b,off)[0]
  if val in targets:pointer_slots[BASE+off]=val
 rows=[]
 for off in range(0,len(b)-3,4):
  ins=struct.unpack_from('<I',b,off)[0]
  if ins&0x0f7f0000!=0x051f0000:continue
  pc=BASE+off+8
  slot=pc+(ins&4095 if ins&0x800000 else -(ins&4095))
  if slot not in pointer_slots:continue
  rows.append((targets[pointer_slots[slot]],f'0x{pointer_slots[slot]:08x}',f'0x{slot:08x}',f'0x{BASE+off:08x}'))
 if a.csv:
  w=csv.writer(sys.stdout);w.writerow(('scene_path','string_va','pointer_slot_va','ldr_va'));w.writerows(rows)
 else:
  for row in rows:print(' | '.join(row))
  print(f'{len(rows)} verified ARM literal xrefs for {len(TARGETS)} named paths')
 print('NOTE: node path reference != event-to-scene binding',file=sys.stderr)
if __name__=='__main__':main()
