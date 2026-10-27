"""Feed every firmware material pair to glhost as the guest would and check linking.

Uses glhost's own stdin protocol (op 7 create shader, 110 shader binary, 102/103
status queries), so it exercises the cache lookup and the blend metadata path.
Usage: check_glhost.py [GLHOST]   (MHI2_SHADER_CACHE is taken from the environment)
"""
import sys
sys.dont_write_bytecode = True
import json
import struct
import subprocess
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
ART = REPO / 'build_fpk1/research-artifacts'


def u(*v):
    return struct.pack('<' + 'I' * len(v), *v)


def main():
    glhost = sys.argv[1] if len(sys.argv) > 1 else str(REPO / 'build_fpk1/bridge/glhost')
    manifest = json.loads((ART / 'shader-audit/manifest.json').read_text())
    log = (ART / 'shader-translate/check-glhost.log').open('wb')
    p = subprocess.Popen([glhost], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)

    def send(op, data=b''):
        p.stdin.write(u(op, len(data)) + data)
        p.stdin.flush()

    def query(op, data):
        send(op, data)
        return struct.unpack('<i', p.stdout.read(4))[0]

    send(1, u(16, 16))
    seen, results, sid = set(), [], 0
    for container in manifest['containers']:
        for pair in container['pairs']:
            keys = tuple(s['key'] for s in pair['stages'])
            if keys in seen:
                continue
            seen.add(keys)
            ids, compiled = [], []
            for stage, key in zip(pair['stages'], keys):
                sid += 1
                ids.append(sid)
                binary = (ART / 'shader-audit/binaries' / f'{key}.bin').read_bytes()
                send(7, u(sid, 0x8b31 if stage['stage'] == 'vertex' else 0x8b30))
                send(110, u(1, 0x890b, len(binary), sid) + binary)
                compiled.append(query(102, u(sid, 0x8b81)))
            sid += 1
            send(10, u(sid))
            send(11, u(sid, ids[0]))
            send(11, u(sid, ids[1]))
            send(12, u(sid))
            linked = query(103, u(sid, 0x8b82)) == 1
            results.append(dict(material=pair['material'], keys=keys, compiled=compiled, linked=linked))
    p.stdin.close()
    p.wait(timeout=30)
    bad = [r for r in results if not r['linked']]
    print(f'glhost linked {len(results) - len(bad)}/{len(results)}')
    for r in bad:
        print(' ', r['material'], r['keys'], r['compiled'])


if __name__ == '__main__':
    main()
