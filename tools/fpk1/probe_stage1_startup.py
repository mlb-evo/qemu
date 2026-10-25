#!/usr/bin/env python3
"""Bounded QEMU experiment with CRC/checksum-verified primary Stage1.

Creates a private temporary boot image and trace, removes both on exit, and
reports metadata only. It does not attach flash/disks or demonstrate QNX boot.
"""
import argparse
import json
from pathlib import Path
import re
import select
import subprocess
import tempfile
import time

from inspect_stage1_framed import decode_archive, startup_layout
from inspect_stage2_catalogs import parse_catalog


def receive(proc):
    ready, _, _ = select.select([proc.stdout], [], [], 5)
    if not ready:
        raise RuntimeError('QMP response timeout')
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError('QEMU closed QMP: ' + proc.stderr.read(8192).decode(errors='replace'))
    return json.loads(line)


def qmp(proc, name, arguments=None):
    request = dict(execute=name)
    if arguments is not None:
        request['arguments'] = arguments
    proc.stdin.write(json.dumps(request).encode() + b'\n')
    proc.stdin.flush()
    for _ in range(100):
        result = receive(proc)
        if 'error' in result:
            raise RuntimeError(str(result['error']))
        if 'return' in result:
            return result['return']
    raise RuntimeError('Too many QMP events')


def probe(archive, qemu, run_ms=200, cbar=None):
    if not 1 <= run_ms <= 2000 or (cbar is not None and not 0 <= cbar <= 0xffffffff):
        raise ValueError('Invalid experiment duration or CBAR')
    decoded, framing = decode_archive(archive)
    layout = startup_layout(decoded)
    parse_catalog(decoded[layout['decoded_imagefs_offset']:])
    load = layout['implied_load_address']
    with tempfile.TemporaryDirectory(prefix='fpk1-startup-') as directory:
        root = Path(directory)
        bios, trace = root / 'boot.bin', root / 'trace.log'
        bios.write_bytes(decoded)
        bios.chmod(0o600)
        end = int(load, 16) + layout['decoded_imagefs_offset'] - 1
        command = [str(Path(qemu).resolve()), '-machine', f'fpk1,load={load},entry={load}',
                   '-m', '512M', '-bios', str(bios), '-display', 'none', '-serial', 'none',
                   '-monitor', 'none', '-nic', 'none', '-S', '-qmp', 'stdio',
                   '-d', 'in_asm,int', '-dfilter', f'{load}..{end:#x}', '-D', str(trace)]
        if cbar is not None:
            command += ['-global', f'cortex-a9-arm-cpu.reset-cbar={cbar:#x}']
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=0)
        try:
            if 'QMP' not in receive(proc):
                raise RuntimeError('Missing QMP greeting')
            qmp(proc, 'qmp_capabilities')
            cpus = qmp(proc, 'query-cpus-fast')
            avps = [cpu['cpu-index'] for cpu in cpus if cpu.get('qom-path', '').endswith('/avp')]
            if len(avps) != 1:
                raise RuntimeError('Missing unique diagnostic AVP CPU')
            cpu = avps[0]
            def registers():
                return qmp(proc, 'human-monitor-command',
                           {'command-line': 'info registers', 'cpu-index': cpu}).split('s00=')[0]
            before = registers()
            started = time.monotonic()
            qmp(proc, 'cont')
            stop_reason = 'duration'
            while time.monotonic() - started < run_ms / 1000:
                if trace.exists() and trace.stat().st_size >= 256 * 1024:
                    stop_reason = 'trace_limit'
                    break
                time.sleep(.001)
            qmp(proc, 'stop')
            elapsed = time.monotonic() - started
            after = registers()
            qmp(proc, 'quit')
            _, stderr = proc.communicate(timeout=5)
            # Read a bounded prefix even if the guest produced more trace between polls.
            trace_size = trace.stat().st_size
            with trace.open('r') as stream:
                text = stream.read(1024 * 1024)
            addresses = re.findall(r'^0x([0-9a-f]+):', text, re.M)
            exception_at = text.find('Taking exception')
            return dict(decoded_sha256=framing['decoded_sha256'], load_address=load,
                        entry_address=load, startup_target=layout['header']['startup_vaddr'],
                        cpu_index=cpu, cbar_override=hex(cbar) if cbar is not None else None,
                        requested_run_ms=run_ms, elapsed_host_ms=round(elapsed * 1000, 3),
                        stopped_for=stop_reason, registers_before=before, registers_after=after,
                        trace_bytes=trace_size, traced_block_count=len(addresses),
                        first_block_addresses=addresses[:10], last_block_addresses=addresses[-10:],
                        first_exception=text[exception_at:].splitlines()[:4] if exception_at >= 0 else [],
                        stderr=stderr.decode(errors='replace'), qemu_exit_status=proc.returncode,
                        limitations=['Diagnostic CPU is the existing AVP model, not proven hardware handoff.',
                                     'No flash or disks are attached; no claim of kernel or service startup.'])
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--qemu', required=True, type=Path)
    parser.add_argument('--run-ms', type=int, default=200)
    parser.add_argument('--cbar', type=lambda value: int(value, 0))
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    output = json.dumps(probe(args.archive, args.qemu, args.run_ms, args.cbar), indent=2) + '\n'
    print(output, end='')
    if args.json:
        args.json.write_text(output)


if __name__ == '__main__':
    main()
