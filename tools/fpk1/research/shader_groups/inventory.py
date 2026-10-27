"""Rank shader groups by distinct firmware material references; local research."""
import sys
sys.dont_write_bytecode=True
import collections,json,re
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
ART=REPO/'build_fpk1/research-artifacts'
OUT=ART/'shader_groups';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(REPO/'tools/fpk1/research/cgdrv-experiment/gear'))
from decode_fragment import decode
from lift_vertex import lift
manifest=json.loads((ART/'shader-audit/manifest.json').read_text())
cache=ART/'cgdrv-experiment/gear/shader-cache';groups=collections.defaultdict(list);rows=[]
for key,p in manifest['programs'].items():
 binary=ART/'shader-audit/binaries'/f'{key}.bin'
 row={'key':key,'stage':p['stage'],'references':len(p['uses']),'materials':sorted({m for u in p['uses'] for m in u['material']}),'cached':(cache/f'{key}.glsl').exists()}
 if p['stage']=='vertex':
  try:source,ir=lift(binary);row['liftable']=True
  except (ValueError,KeyError,AssertionError,IndexError) as e:row.update(liftable=False,rejection=str(e))
 else:
  try:
   ir=decode(binary.read_bytes());a=ir['arrays'];signature={'packets':len(ir['packets']),'texture':a['0x701'],'mfu':a['0x604'],'opcodes':[[x['opcode'] for x in p] for p in ir['packets']]};sig=json.dumps(signature,sort_keys=True);groups[sig].append(row);row['signature']=signature
  except (ValueError,KeyError,AssertionError,IndexError) as e:row['rejection']=str(e)
 rows.append(row)
ranked=sorted(rows,key=lambda r:r['references'],reverse=True)
group_rows=sorted([dict(signature=json.loads(s),programs=items,program_count=len(items),references=sum(i['references'] for i in items)) for s,items in groups.items()],key=lambda r:r['references'],reverse=True)
(OUT/'inventory.json').write_text(json.dumps({'programs':ranked,'fragment_groups':group_rows},indent=2)+'\n')
print('Top unhandled programs:')
for r in [r for r in ranked if not r['cached']][:15]:print(r['key'],r['stage'],r['references'],r['materials'][:5],r.get('liftable',''))
print('Top fragment groups:')
for i,g in enumerate(group_rows[:8]):print(i,g['program_count'],g['references'],g['signature'],g['programs'][0]['key'])
