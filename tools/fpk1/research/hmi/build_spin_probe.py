"""Build an isolated GLES polling experiment; never replace the working bridge."""
import sys
sys.dont_write_bytecode = True
import argparse
from pathlib import Path
import re
import subprocess

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reply-spins', type=int, default=65536)
    p.add_argument('--lock-spins', type=int, default=4096)
    p.add_argument('--sleep-us', type=int, default=1000)
    p.add_argument('--sleep-bench', action='store_true', help='measure usleep(0/1/100/1000) once per EGL client')
    a = p.parse_args()
    if min(a.reply_spins, a.lock_spins) < 1 or a.sleep_us < 0:
        p.error('spin counts must be positive; sleep must be non-negative')
    source = REPO / 'tools/mhi2/glforward/guest'
    key = f'{a.reply_spins}-{a.lock_spins}'
    if a.sleep_us != 1000 or a.sleep_bench:
        key += f'-sleep{a.sleep_us}' + ('-bench' if a.sleep_bench else '')
    out = REPO / 'build_fpk1/research-artifacts/stage3-spin' / key
    out.mkdir(parents=True, exist_ok=True)
    header = (source / 'bridge_transport.h').read_text()
    header, replies = re.subn(r'\+\+spins < \d+', f'++spins < {a.reply_spins}', header)
    header, locks = re.subn(r'\+\+spins>=\d+', f'++spins>={a.lock_spins}', header)
    assert (replies, locks) == (1, 1)
    header = header.replace('usleep(1000)', f'usleep({a.sleep_us})')
    (out / 'bridge_transport.h').write_text(header)
    shim = (source / 'gl_shim.c').read_text()
    if a.sleep_bench:
        marker = 'u32 eglInitialize(void *dpy, i32 *major, i32 *minor)\n{'
        assert shim.count(marker) == 1
        bench = '''
    static int bench_done;
    if (!bench_done++) {
        struct ProbeTimeval { long sec, usec; } before, after;
        extern int gettimeofday(struct ProbeTimeval *, void *);
        const unsigned waits[] = {0, 1, 100, 1000};
        for (unsigned i = 0; i < 4; ++i) {
            char line[128];
            gettimeofday(&before, 0);
            usleep(waits[i]);
            gettimeofday(&after, 0);
            long elapsed = (after.sec - before.sec) * 1000000 + after.usec - before.usec;
            int n = snprintf(line, sizeof(line), "sleep-probe pid %d requested %u us actual %ld us\\n",
                             getpid(), waits[i], elapsed);
            write(2, line, n);
        }
    }
'''
        shim = shim.replace(marker, marker + bench)
    (out / 'gl_shim.c').write_text(shim)
    subprocess.run(['arm-none-eabi-gcc', '-mfloat-abi=soft', '-mcpu=cortex-a9', '-marm',
                    '-fPIC', '-ffreestanding', '-fno-builtin', '-O2',
                    '-DGLBRIDGE_DEFAULT_W=1440', '-DGLBRIDGE_DEFAULT_H=540',
                    '-I', str(source), '-c', str(out / 'gl_shim.c'), '-o', str(out / 'gl-shim.o')], check=True)
    for name in ('libGLESv2.so', 'libEGL.so'):
        subprocess.run(['arm-none-eabi-ld', '-shared', '--hash-style=sysv', '-soname', name,
                        '-o', str(out / name), str(out / 'gl-shim.o')], check=True)
    print(out)


if __name__ == '__main__':
    main()
