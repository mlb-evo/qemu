#!/usr/bin/env python3
"""Firmware-free checks of the opt-in FPK1 read-only NOR diagnostic backing."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from probe_stage1_startup import qmp, receive, parse_registers


def check(qemu):
    with tempfile.TemporaryDirectory(prefix='fpk1-nor-check-') as directory:
        root = Path(directory)
        boot, nor = root / 'boot.bin', root / 'nor.bin'
        # Read NOR; try overwriting it; read again; inspect erased tail; mark completion.
        code = (0xe3003000, 0xe3443800, 0xe5930000, 0xe3e01000, 0xe5831000,
                0xe5932000, 0xe5935100, 0xe306400d, 0xeafffffe)
        boot.write_bytes(struct.pack('<9I', *code))
        nor.write_bytes(struct.pack('<I', 0x12345678))
        cmd = [str(qemu.resolve()), '-machine',
               f'fpk1,load=0x80010000,entry=0x80010000,nor-image={nor}',
               '-bios', str(boot), '-m', '512M', '-display', 'none', '-serial', 'none',
               '-monitor', 'none', '-nic', 'none', '-accel', 'tcg,thread=single']
        with (root / 'stderr').open('wb') as stderr:
            proc = subprocess.Popen(cmd + ['-S', '-qmp', 'stdio'], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=stderr, bufsize=0)
            try:
                assert 'QMP' in receive(proc)
                qmp(proc, 'qmp_capabilities')
                cpu = next(c['cpu-index'] for c in qmp(proc, 'query-cpus-fast') if c['qom-path'].endswith('/avp'))
                for _ in range(2):
                    qmp(proc, 'cont')
                    time.sleep(.1)
                    qmp(proc, 'stop')
                    state = qmp(proc, 'human-monitor-command', {'command-line': 'info registers', 'cpu-index': cpu})
                    regs = parse_registers(state)
                    assert regs.get(4) == 0x600d, 'NOR test did not complete'
                    assert regs.get(0) == regs.get(2) == 0x12345678, 'NOR read/write protection failed'
                    assert regs.get(5) == 0xffffffff, 'Unloaded NOR tail must read as erased'
                    qmp(proc, 'system_reset')
                qmp(proc, 'quit')
                proc.communicate(timeout=5)
                assert proc.returncode == 0
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
        assert nor.read_bytes() == struct.pack('<I', 0x12345678), 'Backing file changed'
        for size in (0, (64 << 20) + 1):
            with nor.open('wb') as stream:
                stream.truncate(size)
            rejected = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            assert rejected.returncode != 0 and 'nor-image must contain' in rejected.stderr, rejected.stderr
    print('NOR mapping, guest write protection, erased tail, reset, unchanged backing and invalid sizes passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', required=True, type=Path)
    check(parser.parse_args().qemu)


if __name__ == '__main__':
    main()
