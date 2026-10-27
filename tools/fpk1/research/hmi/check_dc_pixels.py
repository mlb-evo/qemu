"""Exercise real QEMU DC scanout with known guest pixels through qtest/QMP.

No firmware is executed. A tiny diagnostic BIOS and all results live under
research-artifacts. Run using the build venv Python after rebuilding QEMU.
"""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

sys.dont_write_bytecode = True
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from probe_stage1_startup import qmp, receive
from PySide6.QtGui import QImage


def main():
    out = REPO / 'build_fpk1/research-artifacts/scanout-pixel-check'
    out.mkdir(parents=True, exist_ok=True)
    bios = out / 'loop.bin'
    bios.write_bytes(bytes.fromhex('feffffea'))
    sock = out / 'qtest.sock'
    sock.unlink(missing_ok=True)
    command = [str(REPO / 'build-fpk1/qemu-build/qemu-system-arm'),
               '-machine', 'fpk1,load=0x80000000,entry=0x80000000',
               '-m', '512M', '-bios', str(bios), '-display', 'none',
               '-S', '-qmp', 'stdio', '-qtest', f'unix:{sock},server=on,wait=off',
               '-qtest-log', '/dev/null', '-nic', 'none']
    with (out / 'stderr.log').open('wb') as error:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=error, bufsize=0)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(5)
        try:
            assert 'QMP' in receive(proc)
            qmp(proc, 'qmp_capabilities')
            for attempt in range(50):
                try:
                    client.connect(str(sock))
                    break
                except FileNotFoundError:
                    time.sleep(.05)
            stream = client.makefile('rwb', buffering=0)

            def qt(command):
                stream.write(command.encode() + b'\n')
                while True:
                    reply = stream.readline()
                    if reply.startswith(b'OK'):
                        return
                    if not reply.startswith(b'IRQ '):
                        raise RuntimeError(repr(reply))

            def reg(index, value):
                qt(f'writel {0x54200000 + index * 4:#x} {value:#x}')

            reg(0x42, 0x10)
            reg(0x409, (2 << 16) | 4)
            reg(0x705, (2 << 16) | 4)
            reg(0x703, 13)
            reg(0x70a, 16)
            reg(0x800, 0x81000000)
            reg(0x32, 0x20)
            logical = bytes.fromhex('ff0000ff 00ff00ff 0000ffff ffffffff 00ff00ff ff0000ff ffffffff 0000ffff')
            expected = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255),
                        (0, 255, 0), (255, 0, 0), (255, 255, 255), (0, 0, 255)]
            results = []
            for swap in range(4):
                for flip in (False, True):
                    xor = (0, 1, 3, 2)[swap]
                    rows = [logical[:16], logical[16:]]
                    if flip:
                        rows.reverse()
                    data = b''.join(bytes(row[i ^ xor] for i in range(16)) for row in rows)
                    qt(f'write 0x81000000 {len(data):#x} 0x{data.hex()}')
                    reg(0x701, swap)
                    reg(0x808, 1 if flip else 0)
                    reg(0x700, 0x40010000 | (4 if flip else 0))
                    path = out / f'swap{swap}-flip{int(flip)}.ppm'
                    qmp(proc, 'screendump', dict(filename=str(path), format='ppm'))
                    image = QImage(str(path))
                    actual = [image.pixelColor(x, y).getRgb()[:3]
                              for y in range(2) for x in range(4)]
                    assert actual == expected, (swap, flip, actual)
                    state = json.loads(qmp(proc, 'qom-get', dict(
                        path='/machine/soc/dc-a', property='scanout-state')))
                    assert state['windows'][0]['registers']['701'] == swap
                    assert state['windows'][0]['registers']['808'] == int(flip)
                    results.append(dict(swap=swap, flip=flip, pixels=actual))
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
            print('PASS: all 8 byte-swap / vertical-direction combinations preserve the known pixels')
            qmp(proc, 'quit')
            proc.wait(timeout=5)
        finally:
            client.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            sock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
