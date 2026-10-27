"""Locate selected node names in original Stage2 KZBs; local research only.

This checks name presence, not whether Kanzi can instantiate a node at runtime.
Results go under build_fpk1/research-artifacts/resource-audit/.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from inspect_stage2_catalogs import parse_catalog
from verify_sifs_partitions import member, parse_table, verify_part

NODES = ('TabBar_Content_RootLayer', 't_follow_placeholder',
         't_DTM_ETA_placeholder', 't_hdc_mb', 't_hdc_mb_nar')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip')
    args = parser.parse_args()
    rows = []
    with zipfile.ZipFile(args.archive) as archive:
        nor = member(archive, 'stage2_ifs.img', b'CIFS')
        nand = member(archive, 'stage2_nand.img', b'ESO_BIN\0')
        table = parse_table(nor)
        for partition in table['partitions']:
            image = b''.join(verify_part(
                nor if p['storage'] == 0 else nand,
                table['data_base'] + p['offset'] if p['storage'] == 0 else p['offset'] - 0x200000,
                p, True)[1] for p in partition['parts'])
            for entry in parse_catalog(image)['entries']:
                if entry['kind'] != 'regular' or not entry['path'].endswith('.kzb'):
                    continue
                data = image[entry['offset']:entry['offset'] + entry['size']]
                rows.append(dict(partition=partition['name'], path=entry['path'],
                                 size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                 names={name: data.count(name.encode()) for name in NODES}))
    report = dict(archive=str(args.archive.resolve()),
                  scope='Stage2 KZB byte-string presence; not runtime node validity', resources=rows)
    out = REPO / 'build_fpk1/research-artifacts/resource-audit'
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'node-presence.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    for row in rows:
        found = [name for name, count in row['names'].items() if count]
        if found:
            print(row['path'] + ': ' + ', '.join(found))
    print(f'{len(rows)} KZBs checked; report: {target}')


if __name__ == '__main__':
    main()
