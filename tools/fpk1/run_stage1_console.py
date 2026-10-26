#!/usr/bin/env python3
"""Longer FPK1 Stage1 runs that record the UART and unimplemented MMIO only.

Uses the same verified decoded Stage1, synthetic CPU0/ATAG handoff and optional
synthetic Stage2 NOR as probe_stage1_startup.py, but without instruction traces,
so the guest can run for minutes. Console text is timestamped by host time.
Guest-error/unimp lines are summarized by register address. Temporary boot,
NOR and log files are removed unless --keep-dir is given.
"""
import argparse
import collections
import json
from pathlib import Path
import re
import os
import shutil
import socket
import struct
import sys
import subprocess
import tempfile
import time

from inspect_stage1_framed import decode_archive, parse_boot_script, startup_layout
from inspect_stage2_catalogs import parse_catalog
from probe_stage1_startup import build_atags, qmp, receive, write_stage2_nor, parse_registers

# Quickboot formats nvsku=%03d-%05d-%04d-%03d etc.; values are synthetic.
# Startup accepts projects 61852/61858; display_init/i2s_init need SKU 5 for
# the FPK GPIO/display path. devg-nvgpio drops csi_lock/csi_pass (needed by
# kdgui_2dmgr's capture layer) for project 61852 below board revision 600.
# The real EEPROM-derived values are unknown.
BOARD_CMDLINE = ('mem=512M@0x80000000 nvsku=699-61852-0005-600 SkuVer=A0 '
                 'ProdInfo=699-61852-0005-600 ProdVer=A0 is_e1888=0 emmc_skipinit=1 ')
VERIFIED_SHA256 = 'adec09b69c71719a6e9d5db944e1467c335e3054e1c4aae5c02c7a93b0edd503'
MMIO = re.compile(r'(?P<kind>read|write)[^\n]*?(?:offset|addr(?:ess)?)[ =:]*(?:0x)?(?P<off>[0-9a-fA-F]+)', re.I)


def diag_shell_image(decoded):
    """Copy of the decoded Stage1 whose final ``tinit`` record runs ``ksh``.

    Diagnostic only: login needs an unknown password, so the console getty is
    replaced in the in-memory boot script. The record keeps its size, flags and
    environment; the imagefs additive checksum is rebalanced in its trailer.
    """
    image = bytearray(decoded)
    base = startup_layout(decoded)['decoded_imagefs_offset']
    catalog = parse_catalog(bytes(image[base:]))
    row = next(r for r in catalog['entries'] if r['path'] == 'proc/boot/startup.script')
    start = base + row['offset']
    script = bytes(image[start:start + row['size']])
    record = parse_boot_script(script)[-1]
    if record.get('executable') != '/bin/tinit':
        raise ValueError('Unexpected final boot-script record')
    at, size = start + record['offset'], record['size']
    strings = b''.join(v.encode() + b'\0' for v in ['/bin/ksh', 'ksh'] + record['env'])
    if 12 + len(strings) > size:
        raise ValueError('Replacement does not fit the original record')
    image[at + 10] = 1  # argc
    image[at + 12:at + size] = strings + bytes(size - 12 - len(strings))
    end = len(image)
    total = sum(x[0] for x in struct.iter_unpack('<I', image[base:end])) & 0xffffffff
    word, = struct.unpack_from('<I', image, end - 4)
    struct.pack_into('<I', image, end - 4, (word - total) & 0xffffffff)
    return bytes(image)


def summarize_log(text, limit=64):
    """Group unimp/guest_errors lines, replacing numbers after the first offset."""
    counts = collections.Counter()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        key = re.sub(r'(value|data|val)\s*[=:]?\s*0x[0-9a-fA-F]+', r'\1=*', line)
        counts[key] += 1
    return [dict(line=k, count=v) for k, v in counts.most_common(limit)]


def run(archive, qemu, seconds, *, stage2_nor=True, tcg_thread='single', icount_shift=None,
        emmc=None, extra=(), keep_dir=None, cmdline='mem=512M@0x80000000 ', log_limit_mib=64, progress=None,
        shell=(), shell_interval=4.0, diag_shell=False, screendump=None,
        replacements=None, glhost=None, gl_frames=None, viewer=False):
    if not 1 <= seconds <= 3600 or tcg_thread not in ('single', 'multi'):
        raise ValueError('Invalid run configuration')
    decoded, framing = decode_archive(archive)
    if framing['decoded_sha256'] != VERIFIED_SHA256:
        raise ValueError('Only the verified primary Stage1 profile is supported')
    layout = startup_layout(decoded)
    load = layout['implied_load_address']
    root = Path(tempfile.mkdtemp(prefix='fpk1-console-'))
    try:
        bios, tags, console, log, errors, serial = (root / n for n in (
            'boot.bin', 'atags.bin', 'console.log', 'qemu.log', 'stderr.log', 'serial.sock'))
        bios.write_bytes(diag_shell_image(decoded) if diag_shell else decoded)
        tags.write_bytes(build_atags(cmdline))
        machine = f'fpk1,load={load},entry={load}'
        nor = None
        if stage2_nor:
            nor = write_stage2_nor(archive, root / 'nor.bin', replacements)
            machine += ',nor-image=' + str(root / 'nor.bin')
        command = [str(Path(qemu).resolve()), '-machine', machine, '-m', '512M',
                   '-bios', str(bios), '-display', 'none',
                   '-chardev', f'socket,id=ser0,path={serial},server=on,wait=off,logfile={console}',
                   '-serial', 'chardev:ser0',
                   '-monitor', 'none', '-nic', 'none', '-S', '-qmp', 'stdio',
                   '-d', 'unimp,guest_errors', '-D', str(log),
                   '-accel', 'tcg,thread=' + tcg_thread,
                   '-device', f'loader,file={tags},addr=0x80000100,force-raw=on',
                   '-device', f'loader,addr={load},cpu-num=0']
        if icount_shift is not None:
            command += ['-icount', f'shift={icount_shift}']
        if emmc:
            command += ['-drive', f'if=sd,index=0,format=raw,file={emmc},snapshot=on']
        helper, viewers = None, []
        if glhost:
            # Same pipe transport as tools/mhi2/debug_shell_local.py.
            for name in ('gl.in', 'gl.out'):
                os.mkfifo(root / name, 0o600)
            gl_in = os.open(root / 'gl.in', os.O_RDWR)
            gl_out = os.open(root / 'gl.out', os.O_RDWR)
            env = dict(os.environ)
            if gl_frames:
                # Primary frame and one dump per guest client, for view_frames.py.
                gl_frames.mkdir(parents=True, exist_ok=True)
                env.update(MHI2_GL_FRAME=str(gl_frames / 'primary.ppm'), MHI2_GL_DUMP_CLIENTS='1',
                           MHI2_GL_CLIENT_DIR=str(gl_frames))
            helper = subprocess.Popen([str(glhost)], stdin=gl_out, stdout=gl_in,
                                      stderr=(root / 'glhost.log').open('wb'), cwd=root, env=env)
            if gl_frames and viewer:
                viewers.append(subprocess.Popen(
                    [sys.executable, str(Path(__file__).with_name('view_frames.py')),
                     '--frame', str(gl_frames / 'primary.ppm'), '--client-dir', str(gl_frames)]))
            command += ['-chardev', f'pipe,id=glbridge,path={root / "gl"}']
        command += list(extra)
        lines, offset, stop = [], 0, 'duration'
        with errors.open('wb') as error_stream:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=error_stream, bufsize=0)
            try:
                if 'QMP' not in receive(proc):
                    raise RuntimeError('Missing QMP greeting')
                qmp(proc, 'qmp_capabilities')
                cpus = qmp(proc, 'query-cpus-fast')
                cpu0 = next(c for c in cpus if c['qom-path'].endswith('/cpu[0]'))
                avp = next(c for c in cpus if c['qom-path'].endswith('/avp'))
                qmp(proc, 'qom-set', dict(path=cpu0['qom-path'], property='start-powered-off', value=False))
                qmp(proc, 'qom-set', dict(path=avp['qom-path'], property='start-powered-off', value=True))
                qmp(proc, 'system_reset')
                # Stay connected and drain the socket so guest UART output never
                # blocks; the chardev logfile keeps the transcript.
                uart = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                uart.connect(str(serial))
                uart.setblocking(False)
                queue, login_at, next_send = list(shell), None, None
                started = time.monotonic()
                qmp(proc, 'cont')
                pending = b''
                while time.monotonic() - started < seconds:
                    if proc.poll() is not None:
                        stop = 'qemu_exit'
                        break
                    if log.exists() and log.stat().st_size > log_limit_mib << 20:
                        stop = 'log_limit'
                        break
                    if console.exists():
                        with console.open('rb') as stream:
                            stream.seek(offset)
                            chunk = stream.read()
                        offset += len(chunk)
                        pending += chunk
                        *done, pending = pending.split(b'\n')
                        for raw in done:
                            text = raw.decode('latin-1').rstrip('\r')
                            lines.append(dict(t=round(time.monotonic() - started, 2), text=text))
                            if progress:
                                progress(lines[-1])
                    try:
                        while uart.recv(65536):
                            pass
                    except BlockingIOError:
                        pass
                    now = time.monotonic()
                    prompt = (b'login:', b'# ') if diag_shell else (b'login:',)
                    recent = pending + b''.join(l['text'].encode('latin-1') for l in lines[-5:])
                    if queue and login_at is None and any(p in recent for p in prompt):
                        login_at, next_send = now, now + 1
                    if queue and next_send is not None and now >= next_send:
                        entry = queue.pop(0)
                        uart.sendall(entry.encode() + b'\r')
                        lines.append(dict(t=round(now - started, 2), text='>>> ' + entry))
                        if progress:
                            progress(lines[-1])
                        next_send = now + shell_interval
                    time.sleep(.2)
                uart.close()
                if pending:
                    lines.append(dict(t=round(time.monotonic() - started, 2), text=pending.decode('latin-1')))
                elapsed = time.monotonic() - started
                pcs = {}
                if proc.poll() is None:
                    qmp(proc, 'stop')
                    if screendump:
                        # Default graphic console (the first display controller,
                        # dc-a); SoC children have no qdev id for device=.
                        try:
                            qmp(proc, 'screendump', dict(filename=f'{screendump}.ppm', format='ppm'))
                        except RuntimeError as error:
                            lines.append(dict(t=None, text=f'screendump: {error}'))
                    for c in cpus:
                        state = qmp(proc, 'human-monitor-command',
                                    {'command-line': 'info registers', 'cpu-index': c['cpu-index']})
                        regs = parse_registers(state)
                        mode = re.search(r'PSR=\S+ \S+ \S+ \S+ (\w+)', state)
                        pcs[c['qom-path'].rsplit('/', 1)[-1]] = dict(
                            pc=hex(regs.get(15, 0)), lr=hex(regs.get(14, 0)),
                            mode=mode.group(1) if mode else None)
                    qmp(proc, 'quit')
                    proc.communicate(timeout=10)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=10)
                for window in viewers:
                    window.terminate()
                if helper is not None:
                    helper.terminate()
                    try:
                        helper.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        helper.kill()
        text = log.read_text(errors='replace') if log.exists() else ''
        return dict(decoded_sha256=framing['decoded_sha256'], command_tail=command[command.index('-accel'):],
                    atag_cmdline=cmdline, diag_shell=diag_shell, requested_s=seconds, elapsed_s=round(elapsed, 2), stopped_for=stop,
                    qemu_exit_status=proc.returncode, nor_backing=nor, emmc_image=str(emmc) if emmc else None,
                    console=lines, cpu_samples=pcs,
                    mmio_log_bytes=len(text), mmio_summary=summarize_log(text),
                    stderr=errors.read_text(errors='replace')[-4000:],
                    limitations=['Synthetic CPU0/ATAG handoff and synthetic read-only NOR; not a bootloader model.',
                                 'Console lines show guest output only; absence of a line is not proof of failure.'])
    finally:
        if keep_dir:
            keep_dir.mkdir(parents=True, exist_ok=True)
            for name in ('console.log', 'qemu.log', 'stderr.log', 'glhost.log'):
                if (root / name).exists():
                    shutil.copy(root / name, keep_dir / name)
        shutil.rmtree(root, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--qemu', required=True, type=Path)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--no-nor', action='store_true', help='do not attach synthetic Stage2 NOR')
    parser.add_argument('--tcg-thread', default='single', choices=('single', 'multi'))
    parser.add_argument('--icount-shift', type=int)
    parser.add_argument('--emmc', type=Path, help='raw eMMC image, attached with snapshot=on')
    parser.add_argument('--cmdline', default='mem=512M@0x80000000 ',
                        help='synthetic ATAG command line (keep the trailing space after mem=)')
    parser.add_argument('--board-info', action='store_true',
                        help='use the synthetic Quickboot-style nvsku/SKU5 command line')
    parser.add_argument('--shell', type=Path,
                        help='file of lines sent to the serial console after login: (e.g. root, then commands)')
    parser.add_argument('--diag-shell', action='store_true',
                        help='run ksh instead of tinit/login on the console (in-memory script change)')
    parser.add_argument('--shell-interval', type=float, default=4.0, help='seconds between shell lines')
    parser.add_argument('--screendump', type=Path, help='PPM path prefix for a final dump of the first display console')
    parser.add_argument('--stage2-replace', action='append', default=[], metavar='PATH=FILE',
                        help='replace a STAGE2.1 file in the synthetic NOR (e.g. lib/libEGL.so=shim.so)')
    parser.add_argument('--glhost', type=Path, help='host GLES renderer bound to the glbridge chardev')
    parser.add_argument('--gl-frames', type=Path,
                        help='directory for glhost primary and per-client frames')
    parser.add_argument('--viewer', action='store_true',
                        help='open tools/fpk1/view_frames.py on --gl-frames during the run')
    parser.add_argument('--keep-dir', type=Path, help='copy console/QEMU logs here')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    if args.viewer and not args.gl_frames:
        parser.error('--viewer needs --gl-frames')
    result = run(args.archive, args.qemu, args.seconds, stage2_nor=not args.no_nor,
                 tcg_thread=args.tcg_thread, icount_shift=args.icount_shift, emmc=args.emmc,
                 keep_dir=args.keep_dir, cmdline=BOARD_CMDLINE if args.board_info else args.cmdline,
                 shell=args.shell.read_text().splitlines() if args.shell else (),
                 shell_interval=args.shell_interval, diag_shell=args.diag_shell, screendump=args.screendump,
                 replacements={p: Path(f).read_bytes() for p, f in (r.split('=', 1) for r in args.stage2_replace)},
                 glhost=args.glhost, gl_frames=args.gl_frames, viewer=args.viewer, progress=lambda l: print(f"[{l['t']:7.2f}] {l['text']}", flush=True))
    text = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(text + '\n')
    else:
        print(text)


if __name__ == '__main__':
    main()
