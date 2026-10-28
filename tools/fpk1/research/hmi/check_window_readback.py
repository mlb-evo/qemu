"""Check CWM/window readback with a different offscreen target still bound."""
import argparse
import os
from pathlib import Path
import struct
import subprocess


def words(*values):
    return struct.pack('<' + 'I' * len(values), *values)


def main():
    repo = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, default=repo / 'build_fpk1/bridge/glhost')
    args = parser.parse_args()
    out = repo / 'build_fpk1/research-artifacts/blank-screen/readback-check'
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MHI2_GL_FRAME=str(out / 'window.ppm'))
    for key in ('MHI2_GL_NO_PPM', 'MHI2_GL_CAPTURE', 'MHI2_GL_DUMP_CLIENTS'):
        env.pop(key, None)
    with (out / 'host.log').open('wb') as log:
        process = subprocess.Popen([str(args.host.resolve())], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, env=env)

        def send(op, data=b''):
            process.stdin.write(words(op, len(data)) + data)
            process.stdin.flush()

        def query(op, data=b''):
            send(op, data)
            raw = process.stdout.read(4)
            assert len(raw) == 4, 'host closed response stream'
            return raw

        try:
            send(1, words(4, 4))
            send(3, struct.pack('<4f', 0, 0, 1, 1))
            send(4, words(0x4000))
            send(78, words(1, 1))
            send(60, words(0x8d40, 1))
            send(79, words(1, 2))
            send(61, words(0x8d41, 2))
            send(63, words(0x8d41, 0x8056, 4, 4))
            send(64, words(0x8d40, 0x8ce0, 0x8d41, 2))
            assert query(109, words(0x8d40)) == words(0x8cd5)
            send(3, struct.pack('<4f', 1, 0, 0, 1))
            send(4, words(0x4000))
            read = words(0, 0, 1, 1, 0x1908, 0x1401)
            assert query(120, read) == bytes((255, 0, 0, 255))
            assert query(131, read + words(123)) == bytes((0, 0, 255, 255))
            assert query(120, read) == bytes((255, 0, 0, 255)), 'CWM readback changed FBO binding'
            send(5)
            assert query(120, read) == bytes((255, 0, 0, 255)), 'frame dump changed FBO binding'
            assert query(105) == words(0)
            raw = (out / 'window.ppm').read_bytes()
            pixels = raw[raw.index(b'\n255\n') + 5:]
            assert pixels == bytes((0, 0, 255)) * 16, 'window dump read offscreen target'
            print('PASS: CWM and window dump read blue screen; explicit readback stays red; FBO preserved')
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
