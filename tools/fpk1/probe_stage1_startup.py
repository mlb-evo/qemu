#!/usr/bin/env python3
"""Bounded QEMU experiments with verified primary Stage1 and explicit handoff.

Private temporary boot image, synthetic ATAGs, console and traces are removed
on exit. CPU0/ATAG options are diagnostic inputs, not a real bootloader model.
"""
import argparse
import json
from pathlib import Path
import re
import select
import struct
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
        detail = proc.stderr.read(8192).decode(errors='replace') if proc.stderr else 'see captured stderr'
        raise RuntimeError('QEMU closed QMP: ' + detail)
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


def build_atags(command_line, ram_mib=512):
    """Synthetic ARM CORE/MEM/CMDLINE tags, following hw/arm/boot.c."""
    raw = command_line.encode('ascii')
    if not raw or len(raw) > 1023 or any(c < 32 or c > 126 for c in raw):
        raise ValueError('ATAG command line must be 1..1023 printable ASCII bytes')
    if not 1 <= ram_mib <= 2048:
        raise ValueError('Unsupported synthetic RAM size')
    raw += b'\0'
    raw += bytes(-len(raw) % 4)
    return (struct.pack('<5I', 5, 0x54410001, 1, 4096, 0) +
            struct.pack('<4I', 4, 0x54410002, ram_mib << 20, 0x80000000) +
            struct.pack('<2I', 2 + len(raw) // 4, 0x54410009) + raw + bytes(8))


def parse_registers(text):
    return {int(reg): int(value, 16) for reg, value in re.findall(r'R(\d\d)=([0-9a-fA-F]{8})', text)}


def fault_context(text):
    fault = re.search(r'Taking exception \d+ \[(Data Abort|Prefetch Abort|Undefined Instruction)\]', text)
    if fault is None:
        return None
    states = list(re.finditer(r'R00=[^\n]*\n(?:R[^\n]*\n){3}PSR=[^\n]*', text[:fault.start()]))
    state = states[-1].group() if states else ''
    return dict(exception=text[fault.start():].splitlines()[:4],
                registers={f'r{n}': hex(v) for n, v in parse_registers(state).items()},
                precise_instruction_trace=bool(state))


def match_entry_traces(text, image, catalog):
    """Match QEMU execution and raw instruction blocks to linked ELF entries.

    QEMU builds printing assembly without raw OBJD-T bytes cannot supply this
    evidence. Shared entry stubs stay ambiguous; all matching paths are returned.
    This identifies catalog bytes executed at an entry, not successful services.
    """
    executed = {int(address, 16) for address in re.findall(
        r'^Trace \d+: \S+ \[[0-9a-fA-F]+/([0-9a-fA-F]+)/', text, re.M)}
    blocks = {}
    for match in re.finditer(r'^0x([0-9a-fA-F]+):[^\n]*\n((?:OBJD-T: [0-9a-fA-F]+\n)+)', text, re.M):
        raw = bytes.fromhex(''.join(re.findall(r'OBJD-T: ([0-9a-fA-F]+)', match[2])))
        if len(raw) >= 16:
            blocks.setdefault(int(match[1], 16), []).append(raw[:32])
    candidates = []
    for row in catalog['entries']:
        if 'offset' not in row or 'size' not in row:
            continue
        elf = image[row['offset']:row['offset'] + row['size']]
        if len(elf) < 52 or elf[:6] != b'\x7fELF\x01\x01':
            continue
        entry, phoff = struct.unpack_from('<II', elf, 24)
        phsize, phnum = struct.unpack_from('<HH', elf, 42)
        if phsize != 32 or phoff + phnum * 32 > len(elf):
            continue
        for block in blocks.get(entry, []) if entry in executed else []:
            for index in range(phnum):
                kind, offset, va, _, size, _, _, _ = struct.unpack_from('<8I', elf, phoff + index * 32)
                if kind != 1 or not va <= entry or entry - va + len(block) > size:
                    continue
                start = offset + entry - va
                if elf[start:start + len(block)] == block:
                    candidates.append(dict(path=row['path'], entry=hex(entry), matched_bytes=len(block)))
                    break
            else:
                continue
            break
    for row in candidates:
        row['unique_at_entry_within_catalog'] = sum(other['entry'] == row['entry'] for other in candidates) == 1
    return candidates


def probe(archive, qemu, run_ms=200, cbar=None, *, boot_cpu='avp',
          atag_cmdline=None, trace_faults=False, tcg_thread=None,
          kernel_state=False, icount_shift=None, trace_limit_kib=256):
    if (not 1 <= run_ms <= 10000 or boot_cpu not in ('avp', 'cpu0') or
            (cbar is not None and not 0 <= cbar <= 0xffffffff) or
            tcg_thread not in (None, 'single', 'multi') or not 16 <= trace_limit_kib <= 8192 or
            (icount_shift is not None and
             (not 0 <= icount_shift <= 10 or tcg_thread != 'single'))):
        raise ValueError('Invalid experiment configuration')
    tags = build_atags(atag_cmdline) if atag_cmdline is not None else None
    decoded, framing = decode_archive(archive)
    if kernel_state and framing['decoded_sha256'] != (
            'adec09b69c71719a6e9d5db944e1467c335e3054e1c4aae5c02c7a93b0edd503'):
        raise ValueError('Kernel-state addresses only apply to the verified primary Stage1 profile')
    layout = startup_layout(decoded)
    image = decoded[layout['decoded_imagefs_offset']:]
    catalog = parse_catalog(image)
    kernel = next(r for r in catalog['entries'] if r['path'] == 'proc/boot/procnto-smp-instr')
    raw_kernel = image[kernel['offset']:kernel['offset'] + kernel['size']]
    entry, phoff = struct.unpack_from('<II', raw_kernel, 24)
    phnum, = struct.unpack_from('<H', raw_kernel, 44)
    loads = [struct.unpack_from('<8I', raw_kernel, phoff + 32 * i) for i in range(phnum)]
    ranges = [(s[2], s[2] + s[5]) for s in loads if s[0] == 1]
    load = layout['implied_load_address']
    with tempfile.TemporaryDirectory(prefix='fpk1-startup-') as directory:
        root = Path(directory)
        bios, trace, errors, console = (root / n for n in ('boot.bin', 'trace.log', 'stderr.log', 'console.log'))
        bios.write_bytes(decoded)
        bios.chmod(0o600)
        end = int(load, 16) + layout['decoded_imagefs_offset'] - 1
        filters = f'{load}..{end:#x},{entry:#x}..{entry + 128:#x}'
        logging = 'in_asm,int'
        if kernel_state:
            # Avoid logging every startup/SMP spin-loop iteration with exec.
            filters = f'{entry:#x}..{entry + 128:#x},0x100000..0x200000'
            logging += ',exec'
        if trace_faults:
            filters = '0x80a013ac..0x80a0145b,0x80a0cbfc..0x80a0ccfc'
            logging += ',cpu'
        command = [str(Path(qemu).resolve()), '-machine', f'fpk1,load={load},entry={load}',
                   '-m', '512M', '-bios', str(bios), '-display', 'none', '-serial', f'file:{console}',
                   '-monitor', 'none', '-nic', 'none', '-S', '-qmp', 'stdio',
                   '-d', logging, '-dfilter', filters, '-D', str(trace)]
        if icount_shift is not None:
            command += ['-icount', f'shift={icount_shift}']
        if cbar is not None:
            command += ['-global', f'cortex-a9-arm-cpu.reset-cbar={cbar:#x}']
        accel = []
        if tcg_thread:
            accel.append('thread=' + tcg_thread)
        if trace_faults:
            accel.append('one-insn-per-tb=on')
        if accel:
            command += ['-accel', 'tcg,' + ','.join(accel)]
        if tags is not None:
            tagfile = root / 'atags.bin'
            tagfile.write_bytes(tags)
            command += ['-device', f'loader,file={tagfile},addr=0x80000100,force-raw=on']
        if boot_cpu == 'cpu0':
            command += ['-device', f'loader,addr={load},cpu-num=0']
        snapshots, memory, before, after, cpu = [], {}, '', '', None
        actual_cbar, session_error = None, None
        stop_reason, elapsed = 'qemu_exit', 0
        kernel_samples = {}
        with errors.open('wb') as error_stream:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=error_stream, bufsize=0)
            try:
                if 'QMP' not in receive(proc):
                    raise RuntimeError('Missing QMP greeting')
                qmp(proc, 'qmp_capabilities')
                cpus = qmp(proc, 'query-cpus-fast')
                suffix = '/avp' if boot_cpu == 'avp' else '/cpu[0]'
                selected = next(c for c in cpus if c['qom-path'].endswith(suffix))
                cpu = selected['cpu-index']
                if boot_cpu == 'cpu0':
                    avp = next(c for c in cpus if c['qom-path'].endswith('/avp'))
                    for path, off in ((selected['qom-path'], False), (avp['qom-path'], True)):
                        qmp(proc, 'qom-set', dict(path=path, property='start-powered-off', value=off))
                    qmp(proc, 'system_reset')
                actual_cbar = qmp(proc, 'qom-get', dict(path=selected['qom-path'], property='reset-cbar'))
                def registers(index):
                    return qmp(proc, 'human-monitor-command',
                               {'command-line': 'info registers', 'cpu-index': index}).split('s00=')[0]
                before = registers(cpu)
                started = time.monotonic()
                qmp(proc, 'cont')
                stop_reason = 'duration'
                while time.monotonic() - started < run_ms / 1000:
                    if proc.poll() is not None:
                        stop_reason = 'qemu_exit'
                        break
                    if trace.exists() and trace.stat().st_size >= trace_limit_kib * 1024:
                        stop_reason = 'trace_limit'
                        break
                    time.sleep(.001)
                elapsed = time.monotonic() - started
                if proc.poll() is None:
                    qmp(proc, 'stop')
                    after = registers(cpu)
                    for c in cpus:
                        state = registers(c['cpu-index'])
                        pc = parse_registers(state).get(15)
                        snapshots.append(dict(cpu_index=c['cpu-index'], path=c['qom-path'],
                                              registers=state, pc=hex(pc) if pc is not None else None,
                                              pc_in_kernel=pc is not None and any(a <= pc < b for a, b in ranges)))
                    for name, address in (('scu_pointer', 0x80a18f98), ('l1_table', 0x80a1a7ec),
                                          ('l2_table', 0x80a1a794), ('memory_option', 0x80a19f24)):
                        memory[name] = qmp(proc, 'human-monitor-command',
                                           {'command-line': f'xp /8wx {address:#x}', 'cpu-index': cpu})
                    if kernel_state:
                        for name, cmd in (
                                ('cpu_counts', 'x /4wx 0xfe0b5880'),
                                ('syspage_header', 'x /32wx 0xfc410000'),
                                ('smp_mailbox', 'x /4wx 0xfc410148'),
                                ('secondary_callout', 'x /24wx 0xfc411e28'),
                                ('global_timer', 'xp /8wx 0x50040200'),
                                ('private_timer', 'xp /8wx 0x50040600'),
                                ('gic_cpu', 'xp /8wx 0x50040100'),
                                ('gic_distributor', 'xp /4wx 0x50041000')):
                            kernel_samples[name] = qmp(proc, 'human-monitor-command',
                                                       {'command-line': cmd, 'cpu-index': cpu})
                        kernel_samples['per_cpu_mailbox'] = [
                            dict(cpu_index=c['cpu-index'],
                                 words=qmp(proc, 'human-monitor-command', {
                                     'command-line': 'x /4wx 0xfc410148', 'cpu-index': c['cpu-index']}),
                                 translation=qmp(proc, 'human-monitor-command', {
                                     'command-line': 'gva2gpa 0xfc41014c', 'cpu-index': c['cpu-index']}))
                            for c in cpus if c['qom-path'].endswith(tuple(f'/cpu[{i}]' for i in range(4)))]
                    qmp(proc, 'quit')
                proc.communicate(timeout=5)
            except (RuntimeError, BrokenPipeError, OSError, json.JSONDecodeError) as error:
                if proc.poll() is None:
                    raise
                session_error = str(error)
                stop_reason = 'qemu_exit'
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
        text = ''
        if trace.exists():
            with trace.open('r') as stream:
                text = stream.read(trace_limit_kib * 1024 + 65536)
        addresses = re.findall(r'^0x([0-9a-f]+):', text, re.M)
        exception_at = text.find('Taking exception')
        with errors.open('rb') as stream:
            stderr = stream.read(65536).decode(errors='replace')
        with console.open('rb') if console.exists() else open('/dev/null', 'rb') as stream:
            console_text = stream.read(65536).decode(errors='replace')
        return dict(decoded_sha256=framing['decoded_sha256'], load_address=load, entry_address=load,
                    startup_target=layout['header']['startup_vaddr'], kernel_entry=hex(entry),
                    kernel_entry_traced=f'{entry:08x}' in addresses, boot_cpu=boot_cpu, cpu_index=cpu,
                    cbar_override=hex(cbar) if cbar is not None else None,
                    actual_reset_cbar=hex(actual_cbar) if actual_cbar is not None else None,
                    atag_cmdline=atag_cmdline, atag_address='0x80000100' if tags else None,
                    tcg_thread=tcg_thread, trace_faults=trace_faults, icount_shift=icount_shift,
                    kernel_samples=kernel_samples, trace_limit_kib=trace_limit_kib,
                    catalog_entry_trace_matches=match_entry_traces(text, image, catalog),
                    trace_read_truncated=trace.exists() and trace.stat().st_size > trace_limit_kib * 1024 + 65536,
                    low_address_trace_present=any(0x100000 <= int(a, 16) < 0x200000 for a in addresses),
                    requested_run_ms=run_ms, elapsed_host_ms=round(elapsed * 1000, 3), stopped_for=stop_reason,
                    registers_before=before, registers_after=after, cpu_snapshots=snapshots,
                    memory_samples=memory, trace_bytes=trace.stat().st_size if trace.exists() else 0,
                    traced_block_count=len(addresses), first_block_addresses=addresses[:10],
                    last_block_addresses=addresses[-10:],
                    first_exception=text[exception_at:].splitlines()[:4] if exception_at >= 0 else [],
                    first_fault=fault_context(text), stderr=stderr, console=console_text,
                    qemu_exit_status=proc.returncode, session_error=session_error,
                    limitations=['CPU0 and ATAGs are synthetic handoff experiments, not a bootloader model.',
                                 'No flash/disks attached; kernel entry alone does not prove service startup.',
                                 'Low-address instruction traces alone cannot identify a process or prove script execution.',
                                 'Kernel samples use addresses specific to the verified primary Stage1; MMIO reads are CPU0 debug views.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--qemu', required=True, type=Path)
    parser.add_argument('--run-ms', type=int, default=200)
    parser.add_argument('--cbar', type=lambda value: int(value, 0))
    parser.add_argument('--boot-cpu', choices=('avp', 'cpu0'), default='avp')
    tags = parser.add_mutually_exclusive_group()
    tags.add_argument('--atag-cmdline', help='exact synthetic ATAG_CMDLINE, including any trailing delimiter')
    tags.add_argument('--memory-handoff', action='store_true', help='supply mem=512M@0x80000000 with trailing space')
    parser.add_argument('--trace-faults', action='store_true', help='single-instruction traces around the two known faults')
    parser.add_argument('--tcg-thread', choices=('single', 'multi'))
    parser.add_argument('--trace-limit-kib', type=int, default=256, help='stop at 16..8192 KiB of trace (default 256)')
    parser.add_argument('--kernel-state', action='store_true', help='sample verified-profile SMP state and trace low program addresses')
    parser.add_argument('--icount-shift', type=int, help='0..10 instruction-count clock shift; requires --tcg-thread single')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    cmdline = 'mem=512M@0x80000000 ' if args.memory_handoff else args.atag_cmdline
    output = json.dumps(probe(args.archive, args.qemu, args.run_ms, args.cbar,
                             boot_cpu=args.boot_cpu, atag_cmdline=cmdline,
                             trace_faults=args.trace_faults, tcg_thread=args.tcg_thread,
                             kernel_state=args.kernel_state, icount_shift=args.icount_shift, trace_limit_kib=args.trace_limit_kib), indent=2) + '\n'
    print(output, end='')
    if args.json:
        args.json.write_text(output)


if __name__ == '__main__':
    main()
