#!/usr/bin/env python3
"""Inventory GTF2-owned scene assets, node paths and property metadata strings.

This extracts static ELF strings, NOT parsed KZB scene graphs. It intentionally
does not claim a DP-to-node binding based on similar names alone.
"""
import argparse,csv,re,struct,sys
from pathlib import Path
BASE=0x100000
PATTERN=re.compile(rb'[A-Za-z_][A-Za-z0-9_./-]{5,}\x00')
CATEGORIES=(
 ('scene_resource',lambda s:s.endswith('.kzb')),
 ('property_metadata_key',lambda s:'_propertyName' in s),
 ('node_anchor_metadata_key',lambda s:'_anchorPath' in s),
 ('scene_node_path',lambda s:'.' in s and s.startswith(('MV_','RV_','PV_','SV_'))),
 ('scene_event_name',lambda s:s.startswith(('eEventIdAPPIN_','eEventIdINTERN_','eStateId'))),
)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('elf',type=Path)
 p.add_argument('--csv',action='store_true')
 a=p.parse_args();b=a.elf.read_bytes()
 if b[:6]!=b'\x7fELF\x01\x01':p.error('expected little-endian ELF32')
 rows=[]
 for m in PATTERN.finditer(b):
  s=m.group()[:-1].decode('ascii')
  for category,pred in CATEGORIES:
   if pred(s):
    rows.append((f'0x{m.start()+BASE:08x}',category,s))
    break
 if a.csv:
  w=csv.writer(sys.stdout);w.writerow(('string_va','evidence_class','literal'));w.writerows(rows)
 else:
  for category,_ in CATEGORIES:
   sub=[r for r in rows if r[1]==category]
   print(f'{category}: {len(sub)}')
   for va,_,s in sub[:15]:print(f'  {va} {s}')
 print('NOTE: string presence does not establish an instantiated node or DP binding',file=sys.stderr)
if __name__=='__main__':main()
