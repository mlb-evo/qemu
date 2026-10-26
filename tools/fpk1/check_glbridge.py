#!/usr/bin/env python3
"""Firmware-free qtest checks of the fpk1 glbridge record lock.

The lock (register 16) is released after 2 s of guest time without bridge
accesses by its holder, so a client killed mid-record cannot block others.
Polling by waiters must not extend the lease, and unread reply bytes of the
dead client are dropped.
"""
import argparse
import os
from pathlib import Path
import select
import struct
import subprocess
import tempfile

BASE = 0x5f000000
SECOND = 1_000_000_000


def check(qemu):
    with tempfile.TemporaryDirectory(prefix='fpk1-glbridge-') as directory:
        root = Path(directory)
        boot = root / 'boot.bin'
        boot.write_bytes(struct.pack('<I', 0xeafffffe))  # b .
        bridge = root / 'bridge'
        os.mkfifo(str(bridge) + '.in')
        os.mkfifo(str(bridge) + '.out')
        host_in = os.open(str(bridge) + '.in', os.O_RDWR | os.O_NONBLOCK)
        host_out = os.open(str(bridge) + '.out', os.O_RDWR | os.O_NONBLOCK)
        proc = subprocess.Popen(
            [str(qemu), '-machine', 'fpk1,load=0x80010000,entry=0x80010000', '-bios', str(boot),
             '-m', '512M', '-display', 'none', '-serial', 'none', '-monitor', 'none',
             '-accel', 'qtest', '-qtest', 'stdio', '-chardev', f'pipe,id=glbridge,path={bridge}'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        pending = bytearray()

        def q(command):
            proc.stdin.write((command + '\n').encode())
            while b'\n' not in pending:
                if not select.select([proc.stdout], [], [], 5)[0]:
                    raise AssertionError('qtest timeout: ' + command)
                data = os.read(proc.stdout.fileno(), 4096)
                if not data:
                    raise AssertionError('QEMU exited: ' + proc.stderr.read().decode(errors='replace'))
                pending.extend(data)
            line, _, rest = pending.partition(b'\n')
            pending[:] = rest
            assert line.startswith(b'OK'), line
            return line.split()[1:]

        def read(offset):
            return int(q(f'readl {BASE + offset:#x}')[0], 16)

        def step(ns):
            q(f'clock_step {ns}')

        try:
            assert read(0) == 0x474c4252
            assert read(16) == 0, 'lock must be free initially'
            assert read(16) == 1, 'second acquire must report held'
            # Waiters polling the lock do not extend the 2 s lease.
            for _ in range(3):
                step(SECOND // 2)
                assert read(16) == 1, 'lock must stay held within the lease'
            step(SECOND)
            assert read(16) == 0, 'waiter polling must not keep an idle lock'
            os.write(host_in, b'stale reply')
            for _ in range(100):
                if read(8):
                    break
            assert read(8) == len(b'stale reply')
            # Reads of RX count above touched the lease; let it lapse now.
            step(3 * SECOND)
            assert read(8) == 0, 'reply bytes of the dead holder must be dropped'
            assert read(16) == 0, 'idle lock must be released and re-acquirable'
            # An active holder keeps its lock while it accesses the bridge.
            for _ in range(6):
                step(SECOND)
                read(8)
            assert read(16) == 1, 'active holder must keep the lock'
            q(f'writel {BASE + 16:#x} 0')
            assert read(16) == 0, 'explicit unlock must free the lock'
            q(f'writel {BASE + 16:#x} 0')
        finally:
            proc.kill()
            proc.communicate(timeout=5)
            os.close(host_in)
            os.close(host_out)
    print('glbridge lock: acquire, waiter polling, idle release, stale RX drop, active lease and unlock passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', required=True, type=Path)
    check(parser.parse_args().qemu.resolve())


if __name__ == '__main__':
    main()
