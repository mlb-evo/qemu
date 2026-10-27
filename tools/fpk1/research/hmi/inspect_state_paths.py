"""Read-only extraction and static xrefs for HMI startup and KSS RTE input."""
import sys
sys.dont_write_bytecode=True
import json,re,struct,zipfile
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
OUT=REPO/'build_fpk1/research-artifacts/hmi';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(REPO/'tools/fpk1'))
from verify_sifs_partitions import member,parse_table,verify_part
from inspect_stage2_catalogs import parse_catalog
from qnx_elf_disasm import Elf,instructions,annotate
archive=REPO/'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip'
with zipfile.ZipFile(archive) as z:
 nor=member(z,'stage2_ifs.img',b'CIFS');table=parse_table(nor);p=next(p for p in table['partitions'] if p['name']=='STAGE2.1')['parts'][0];_,image=verify_part(nor,table['data_base']+p['offset'],p,True)
 for row in parse_catalog(image)['entries']:
  if row['path'] in ('bin/gtf2','bin/gss_ipc','config/tracing.json'):
   (OUT/Path(row['path']).name).write_bytes(image[row['offset']:row['offset']+row['size']])
report={}
for name,patterns in {'gtf2':['onEmptyViewEntered','updateClamp15State clamp15State','transition lookup for state','executeStateCommands state','SV_Empty_Startup','KSS_Clamps_HMI_Clamp15','setVersionScreenMode'], 'gss_ipc':['RTE incoming event','Clamps','Rte_Read_VersionsScreen','GSS_MODE_REQUEST','registering lun=%ld','RTE Ready for','rteAllDPUpdated','RX data per frame']}.items():
 elf=Elf(OUT/name);targets={}
 for pattern in patterns:
  for match in re.finditer(re.escape(pattern.encode()),elf.data):
   off=match.start();start=elf.data.rfind(b'\0',0,off)+1;end=elf.data.find(b'\0',off)
   if end-start>300:continue
   va=next((p[2]+start-p[1] for p in elf.ph if p[0]==1 and p[1]<=start<p[1]+p[4]),None)
   if va is not None:targets[va]=elf.data[start:end].decode('latin1')
 refs=[]
 for ins in instructions(elf):
  m=re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]',ins.op_str)
  if m and ins.mnemonic.startswith('ldr'):
   value=elf.word(ins.address+8+int(m.group(1),0))
   if value in targets:refs.append(dict(address=hex(ins.address),text=targets[value],string_address=hex(value)))
 report[name]=refs
 (OUT/f'{name}-xref-context.txt').write_text('\n\n'.join(f"STRING {r['text']} at {r['address']}\n"+'\n'.join(annotate(elf,i) for i in instructions(elf,int(r['address'],16)-64,int(r['address'],16)+128)) for r in refs))
(OUT/'state-xrefs.json').write_text(json.dumps(report,indent=2)+'\n')
for name,refs in report.items():
 print(name)
 for r in refs:print(r['address'],r['text'])
