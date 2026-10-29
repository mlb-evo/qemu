"""Exercise the captured telltale fragment binary over a known background."""
import argparse
import os
from pathlib import Path
import struct
import subprocess

repo = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--legacy', action='store_true', help='measure the historical table for comparison')
args = parser.parse_args()
art = repo / 'build_fpk1/research-artifacts'
env = dict(os.environ, MHI2_GL_NO_PPM='1')
if args.legacy:
    env.pop('MHI2_SHADER_CACHE', None)
else:
    env['MHI2_SHADER_CACHE'] = str(art / 'shader-translate/cache')

def words(*values):
    return struct.pack('<' + 'I' * len(values), *values)

with (art / 'icon-render/alpha-check.log').open('wb') as log:
    process = subprocess.Popen([repo / 'build_fpk1/bridge/glhost'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=log, env=env)
    def send(op, payload=b''):
        process.stdin.write(words(op, len(payload)) + payload)
        process.stdin.flush()

    def query(op, payload):
        send(op, payload)
        data = process.stdout.read(4)
        assert len(data) == 4, 'renderer closed response stream'
        return struct.unpack('<i', data)[0]

    try:
        send(1, words(4, 4))
        source = (b'varying highp vec2 vTexCoord;varying highp vec4 vModulate;'
                  b'void main(){gl_Position=vec4(0.,0.,0.,1.);gl_PointSize=4.;'
                  b'vTexCoord=vec2(.5);vModulate=vec4(1.);}')
        send(7, words(1, 0x8b31))
        send(8, words(1, len(source)) + source)
        send(9, words(1))
        assert query(102, words(1, 0x8b81)) == 1
        binary = (art / 'shader-translate/binaries/6d69eec5eb9bcc01-808.bin').read_bytes()
        send(7, words(2, 0x8b30))
        send(110, words(1, 0x890b, len(binary), 2) + binary)
        assert query(102, words(2, 0x8b81)) == 1
        send(10, words(3))
        for shader in (1, 2):
            send(11, words(3, shader))
        send(12, words(3))
        assert query(103, words(3, 0x8b82)) == 1
        send(13, words(3))
        name = b'LayerRenderTexture'
        location = query(101, words(3, len(name)) + name)
        assert location >= 0
        send(30, struct.pack('<ii', location, 0))
        send(50, words(1, 4))
        send(51, words(0xde1, 4))
        for parameter in (0x2800, 0x2801):
            send(53, words(0xde1, parameter, 0x2600))
        pixels = []
        for alpha in (0, 128, 255):
            send(52, words(0xde1, 0, 0x1908, 1, 1, 0, 0x1908, 0x1401, 4) + bytes((255, 0, 0, alpha)))
            send(3, struct.pack('<4f', 0, 0, 1, 1))
            send(4, words(0x4000))
            send(31, words(0, 0, 1))
            send(120, words(2, 2, 1, 1, 0x1908, 0x1401))
            pixel = tuple(process.stdout.read(4))
            pixels.append(pixel)
            if not args.legacy:
                expected = (alpha, 0, 255 - alpha, 255)
                assert all(abs(a-b) <= 1 for a, b in zip(pixel, expected)), (alpha, pixel, expected)
        assert query(105, b'') == 0
        print(('LEGACY' if args.legacy else 'PASS'), 'alpha 0/128/255:', pixels)
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
