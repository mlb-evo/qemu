#!/usr/bin/env python3
"""Firmware-free ARM register-shift regression for the FPK1 QEMU build.

On an AArch64 CSSC host these operations exercise TCG's UMIN lowering, which
previously emitted an invalid instruction. Results also check ARM's low-byte
shift count and saturation rules. Other hosts test semantics via their backend.
"""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from probe_stage1_startup import qmp, receive, parse_registers


def cases():
    for value in (0x80000000, 0x7fffffff):
        for kind in ('lsl', 'lsr', 'asr'):
            for count in (0, 1, 31, 32, 40, 255, 256, 257):
                shift = count & 255
                if kind == 'lsl':
                    expected = (value << shift) & 0xffffffff
                elif kind == 'lsr':
                    expected = value >> shift
                else:
                    signed = value if value < 0x80000000 else value - (1 << 32)
                    expected = (signed >> shift) & 0xffffffff
                yield value, kind, count, expected


def mov16(reg, value, top=False):
    return (0xe3400000 if top else 0xe3000000) | (value >> 12) << 16 | reg << 12 | (value & 0xfff)


def image():
    # r3 = result buffer at 0x80011000; a separate page from the boot code.
    code = [mov16(3, 0x1000), mov16(3, 0x8001, True)]
    for index, (value, kind, count, _) in enumerate(cases()):
        code += [mov16(0, value & 0xffff), mov16(0, value >> 16, True), mov16(1, count),
                 0xeaffffff,  # branch to next instruction: prevent cross-instruction constant folding
                 0xe1a02110 | {'lsl': 0, 'lsr': 1, 'asr': 2}[kind] << 5,
                 0xe5832000 | index * 4]  # mov r2,r0,<kind> r1; str r2,[r3,#offset]
    code += [mov16(4, 0x600d), 0xeafffffe]
    return struct.pack('<' + 'I' * len(code), *code)


def check(qemu):
    with tempfile.TemporaryDirectory(prefix='fpk1-shifts-') as directory:
        root = Path(directory)
        boot = root / 'shifts.bin'
        results = root / 'results.bin'
        boot.write_bytes(image())
        cmd = [str(qemu.resolve()), '-machine', 'fpk1,load=0x80010000,entry=0x80010000',
               '-bios', str(boot), '-m', '512M', '-display', 'none', '-serial', 'none',
               '-monitor', 'none', '-nic', 'none', '-accel', 'tcg,thread=single', '-S', '-qmp', 'stdio']
        with (root / 'stderr').open('wb') as stderr:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, bufsize=0)
            try:
                assert 'QMP' in receive(proc), 'Missing QMP greeting'
                qmp(proc, 'qmp_capabilities')
                cpu = next(c['cpu-index'] for c in qmp(proc, 'query-cpus-fast') if c['qom-path'].endswith('/avp'))
                qmp(proc, 'cont')
                time.sleep(.1)
                qmp(proc, 'stop')
                regs = qmp(proc, 'human-monitor-command', {'command-line': 'info registers', 'cpu-index': cpu})
                assert parse_registers(regs).get(4) == 0x600d, 'Guest did not finish shift cases'
                qmp(proc, 'pmemsave', dict(val=0x80011000, size=48 * 4, filename=str(results)))
                qmp(proc, 'quit')
                proc.communicate(timeout=5)
                assert proc.returncode == 0, f'QEMU exited with {proc.returncode}'
                actual = struct.unpack('<48I', results.read_bytes())
                for observed, (value, kind, count, expected) in zip(actual, cases()):
                    assert observed == expected, (hex(value), kind, count, hex(observed), hex(expected))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
    print('48 ARM register-shift cases passed (LSL/LSR/ASR, sign and count boundaries)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', required=True, type=Path)
    check(parser.parse_args().qemu)


if __name__ == '__main__':
    main()
