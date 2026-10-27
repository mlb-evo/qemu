"""Extract named Stage2 files (e.g. bin/gtf2) from the FPK1 update; local research.

Usage: extract_stage2.py NAME... ; files go to build_fpk1/research-artifacts/stage2/.
"""
import sys
sys.dont_write_bytecode = True
import zipfile
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path[:0] = [str(REPO / 'tools/fpk1'), str(REPO / 'tools/mhi2')]
from verify_sifs_partitions import member, parse_table, verify_part
from inspect_stage2_catalogs import parse_catalog

OUT = REPO / 'build_fpk1/research-artifacts/stage2'
wanted = set(sys.argv[1:])
OUT.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip') as z:
    nor = member(z, 'stage2_ifs.img', b'CIFS')
    nand = member(z, 'stage2_nand.img', b'ESO_BIN\0')
    table = parse_table(nor)
    for partition in table['partitions']:
        image = bytearray()
        for part in partition['parts']:
            data = nor if part['storage'] == 0 else nand
            at = table['data_base'] + part['offset'] if part['storage'] == 0 else part['offset'] - 0x200000
            image.extend(verify_part(data, at, part, True)[1])
        for row in parse_catalog(bytes(image))['entries']:
            if row['kind'] == 'regular' and (row['path'] in wanted or row['path'].split('/')[-1] in wanted):
                target = OUT / partition['name'] / row['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bytes(image[row['offset']:row['offset'] + row['size']]))
                print(target, row['size'])
