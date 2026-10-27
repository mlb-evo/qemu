"""Local read-only FPK1 firmware experiment; outputs stay under build_fpk1."""
import sys
sys.dont_write_bytecode = True
import collections
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zipfile

REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
sys.path[:0] = [str(REPO/'tools/fpk1'), str(REPO/'tools/mhi2')]
from verify_sifs_partitions import member, parse_table, verify_part
from inspect_stage2_catalogs import parse_catalog
from extract_kanzi_shaders import pairs, shader_hash
from qnx6_read import Qnx6

OUT = next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())/'build_fpk1/research-artifacts/shader-audit'
(OUT/'binaries').mkdir(exist_ok=True)
archive = REPO/'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip'
report = {'archive': str(archive), 'containers': [], 'programs': {}, 'source_files': [], 'partitions': {}}

def directory(data):
    end = 0x3c + struct.unpack_from('>I', data, 0x34)[0]
    if end > len(data):
        raise ValueError('Directory exceeds file')
    resources = [None]
    for pos in range(0x3c, end-18):
        off, size, kind, flags, n = struct.unpack_from('>IIIIH', data, pos)
        name = data[pos+18:pos+18+n]
        if (end <= off < len(data) and size <= len(data)-off and
                0 < kind < 10000 and flags == 0 and 0 < n < 256 and
                len(name) == n and all(32 <= c < 127 for c in name)):
            resources.append(dict(offset=off, size=size, kind=kind, name=name.decode()))
    return resources

def inspect(path, data):
    if Path(path).suffix.lower() in ('.glsl','.vert','.frag','.vsh','.fsh','.cg','.cgc'):
        report['source_files'].append({'path':path,'size':len(data),'has_main':b'void main' in data})
    if not path.lower().endswith('.kzb'):
        return
    resources = directory(data)
    src = [r for r in resources[1:] if r['kind'] == 2010]
    row = {'path':path, 'sha256':hashlib.sha256(data).hexdigest(),
           'source_records':len(src), 'nonempty_source_records':sum(r['size']>0 for r in src),
           'void_main_occurrences':data.count(b'void main'), 'pairs':[]}
    try:
        paired = pairs(data)
        row['existing_extractor'] = {'programs':len(paired)}
    except (ValueError, KeyError, struct.error) as exc:
        row['existing_extractor'] = {'rejected':str(exc)}
    for match in re.finditer(rb'Tegra\0\0\0\0\0', data):
        vs, fs, count = struct.unpack_from('<III', data, match.start()-14)
        assert count == 1
        owners = [r for r in resources[1:] if r['kind']==1120 and
                  r['offset'] <= match.start() < r['offset']+r['size']+4]
        pos = match.end()
        pair = {'material':[r['name'] for r in owners], 'stages':[]}
        for stage, ref in [('vertex',vs),('fragment',fs)]:
            assert 0 < ref < len(resources) and resources[ref]['kind']==2010
            source = resources[ref]
            size, = struct.unpack_from('<I',data,pos)
            pos += 4
            binary = data[pos:pos+size]
            pos += size
            assert len(binary)==size and size>=324 and binary[8:12]==bytes.fromhex('18000100')
            key = f'{shader_hash(binary):016x}-{size}'
            pair['stages'].append({'stage':stage,'key':key,'source_ref':ref,'source_size':source['size']})
            if key not in report['programs']:
                report['programs'][key]={'stage':stage,'size':size,'uses':[]}
                (OUT/'binaries'/f'{key}.bin').write_bytes(binary)
            report['programs'][key]['uses'].append({'resource':path,'material':pair['material']})
        row['pairs'].append(pair)
    report['containers'].append(row)

with zipfile.ZipFile(archive) as z:
    nor = member(z,'stage2_ifs.img',b'CIFS')
    nand = member(z,'stage2_nand.img',b'ESO_BIN\0')
    table = parse_table(nor)
    for partition in table['partitions']:
        image = bytearray()
        for part in partition['parts']:
            data = nor if part['storage']==0 else nand
            at = table['data_base']+part['offset'] if part['storage']==0 else part['offset']-0x200000
            _, raw = verify_part(data,at,part,True)
            image.extend(raw)
        entries = parse_catalog(bytes(image))['entries']
        regular = [r for r in entries if r['kind']=='regular']
        report['partitions'][partition['name']]={'regular_files':len(regular)}
        for row in regular:
            inspect(partition['name']+'/'+row['path'],bytes(image[row['offset']:row['offset']+row['size']]))

metadata = json.loads((REPO/'build_fpk1/media/emmc.json').read_text())
for partition in metadata['partitions']:
    if partition['label'] not in ('stage3','app'):
        continue
    fs = Qnx6(str(REPO/'build_fpk1/media/emmc.img'), partition['start_sector']*512)
    count = 0
    def walk(ino=1, path=''):
        global count
        for name, child in fs.listdir(ino):
            if name in ('.','..'):
                continue
            full = path+'/'+name
            if fs.is_dir(child):
                yield from walk(child,full)
            else:
                count += 1
                yield full,fs.read_file(child)
    for path, data in walk():
        inspect(partition['label']+path,data)
    report['partitions'][partition['label']]={'files':count}
    fs.f.close()

log = (REPO/'build_fpk1/runs/20261026-195334/glhost.log').read_text()
unsupported = set(re.findall(r'UNSUPPORTED NVIDIA shader hash=([0-9a-f]+)',log))
found = {key.split('-')[0] for key in report['programs']}
report['coverage'] = {'baseline_unsupported_unique':len(unsupported),
                      'present_in_kzb':len(unsupported & found),
                      'absent_from_kzb':sorted(unsupported-found)}
report['summary'] = {'containers':len(report['containers']),
                     'source_records':sum(r['source_records'] for r in report['containers']),
                     'nonempty_source_records':sum(r['nonempty_source_records'] for r in report['containers']),
                     'binary_pairs':sum(len(r['pairs']) for r in report['containers']),
                     'unique_binaries':len(report['programs'])}
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('summary','coverage','partitions','source_files')},indent=2))
for row in report['containers']:
    for pair in row['pairs']:
        if 'gear_m_Arrow' in pair['material']:
            print('gear_m_Arrow:',row['path'],json.dumps(pair))
