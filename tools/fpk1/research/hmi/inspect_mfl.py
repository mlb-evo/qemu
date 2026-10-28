"""Reproduce Q7 0378 MFL transport/key-table findings from original firmware.

Requires capstone and lzokay. Extracted binaries, disassembly and JSON remain
under build_fpk1/research-artifacts/wheel/; this script performs no VM writes.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
from pathlib import Path
import zipfile

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from inspect_stage2_catalogs import parse_catalog
from verify_sifs_partitions import member, parse_table, verify_part
from qnx_elf_disasm import Elf, instructions, annotate


def main():
    out = REPO / 'build_fpk1/research-artifacts/wheel'
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip') as z:
        nor = member(z, 'stage2_ifs.img', b'CIFS')
        table = parse_table(nor)
        part = next(p for p in table['partitions'] if p['name'] == 'STAGE2.1')['parts'][0]
        _, image = verify_part(nor, table['data_base'] + part['offset'], part, True)
        for row in parse_catalog(image)['entries']:
            if row['path'] in ('bin/gss_ipc', 'bin/gtf2'):
                (out / Path(row['path']).name).write_bytes(image[row['offset']:row['offset'] + row['size']])
    gss, gtf = (Elf(out / name) for name in ('gss_ipc', 'gtf2'))
    descriptor = [gss.word(0x1abdf0 + 0x1cc * 20 + i * 4) for i in range(5)]
    assert descriptor == [0x1cc, 4, 0, 0x1643a8, 0x169700]
    rows = []
    for key in range(0x24):
        idx = gtf.word(0x7da8a4 + key * 4)
        if idx == 16:
            continue
        events = []
        for event in range(1, 7):
            event_id = gtf.word(0x7da5a8 + 4 * (idx * 6 + event - 1))
            if event_id != 0xffffffff:
                events.append(dict(event_code=event, hmi_id=hex(event_id),
                                   name=gtf.cstr(gtf.word(0x752e3c + event_id * 4))))
        rows.append(dict(keycode=key, index=idx,
                         button=bool(gtf.data[gtf.off(0x7d9d30) + idx]), events=events))
    report = dict(sha256={name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                          for name in ('gss_ipc', 'gtf2')},
                  descriptor=[hex(v) for v in descriptor],
                  wire_order=['event1 | event2<<4', 'brand | variant<<4', 'key1', 'key2'],
                  rte_component='0x6e', rte_element=0, keys=rows,
                  roller=dict(key=6, event_1_ticks=-1, event_15_ticks=1),
                  note='Trace formatter fields are bitfields, not six independent bytes.')
    (out / 'mfl.json').write_text(json.dumps(report, indent=2) + '\n')
    for name, elf, ranges in (
        ('gss', gss, ((0x1656b0, 0x1656fc), (0x169700, 0x16972c), (0x13eb30, 0x13ebf0))),
        ('gtf', gtf, ((0x18c82c, 0x18c9a8), (0x18bb88, 0x18be70),
                      (0x18ce04, 0x18cee8), (0x696f4c, 0x696fa0))),
    ):
        (out / f'{name}-mfl-disassembly.txt').write_text('\n\n'.join(
            '\n'.join(annotate(elf, i) for i in instructions(elf, start, end))
            for start, end in ranges) + '\n')
    print(out / 'mfl.json')


if __name__ == '__main__':
    main()
