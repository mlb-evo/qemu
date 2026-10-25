#!/usr/bin/env python3
"""Raw-byte and register evidence for the verified Stage1 storage profile.

Native TB identity separates processes reusing the same guest VA. Only blocks
whose complete bytes match the expected catalog file are used; no process identity is
inferred from a virtual address alone. This consumes QEMU in_asm,exec,cpu logs.
"""
import re
import struct

EMMC_CHECKPOINTS = {
    0x1075bc: 'emmc_main',
    0x107638: 'emmc_io_privilege_return',
    0x107674: 'emmc_cam_configure_return',
    0x107ba4: 'emmc_gpio_mapping_return',
    0x10217c: 'emmc_diagnostic',
}

CHECKPOINTS = {
    **EMMC_CHECKPOINTS,
    0x102a94: 'table_magic_result',
    0x102b48: 'table_version_accepted',
    0x102348: 'table_parse_result',
    0x10312c: 'lzo_return',
    0x10316c: 'lzo_length_accepted_more_blocks',
    0x102954: 'mount_return',
    0x104124: 'diagnostic',
    0x1028e4: 'main_return',
    0x103400: 'nor_read_return',
    0x10313c: 'decompression_error',
    0x10315c: 'decompression_failed',
}

EVENT = re.compile(
    r'^0x(?P<addr>[0-9a-fA-F]+):[^\n]*\n(?P<raw>(?:OBJD-T: [0-9a-fA-F]+\n)+)|'
    r'^Trace (?P<cpu>\d+): (?P<tb>\S+) '
    r'\[[0-9a-fA-F]+/(?P<pc>[0-9a-fA-F]+)/[0-9a-fA-F]+/[0-9a-fA-F]+\] *\n'
    r'(?P<regs>(?:R[^\n]*\n){4}PSR=[^\n]*)', re.M)


def execution_samples(text):
    pending, translated = None, {}
    for match in EVENT.finditer(text):
        if match['addr']:
            raw = ''.join(re.findall(r'OBJD-T: ([0-9a-fA-F]+)', match['raw']))
            if len(raw) % 2:
                pending = None
                continue
            pending = (int(match['addr'], 16), bytes.fromhex(raw))
            continue
        pc = int(match['pc'], 16)
        if pending and pending[0] == pc:
            translated[match['tb']] = pending
            pending = None
        translated_block = translated.get(match['tb'])
        if translated_block is None or translated_block[0] != pc:
            continue
        registers = {int(r): int(v, 16) for r, v in re.findall(
            r'R(\d\d)=([0-9a-fA-F]{8})', match['regs'])}
        yield dict(pc=pc, cpu=int(match['cpu']), code=translated_block[1], registers=registers)


def load_segments(elf):
    if len(elf) < 52 or elf[:6] != b'\x7fELF\x01\x01':
        return []
    phoff, = struct.unpack_from('<I', elf, 28)
    phsize, count = struct.unpack_from('<HH', elf, 42)
    if phsize != 32 or phoff + count * phsize > len(elf):
        return []
    return [struct.unpack_from('<8I', elf, phoff + i * 32) for i in range(count)]


def file_bytes(elf, segments, address, size, executable=False):
    for kind, offset, va, _, stored, _, flags, _ in segments:
        if (kind == 1 and (not executable or flags & 1) and va <= address and
                address - va + size <= stored):
            start = offset + address - va
            if start + size <= len(elf):
                return elf[start:start + size]
    return None


def storage_evidence(text, image, catalog):
    files = []
    for row in catalog['entries']:
        if row.get('kind') != 'regular':
            continue
        raw = image[row['offset']:row['offset'] + row['size']]
        segments = load_segments(raw)
        if segments:
            files.append((row['path'], raw, segments))
    evidence = {}
    for sample in execution_samples(text):
        pc, code, registers = sample['pc'], sample['code'], sample['registers']
        if pc not in CHECKPOINTS or len(code) < 8:
            continue
        owners = [(path, raw, segments) for path, raw, segments in files
                  if file_bytes(raw, segments, pc, len(code), True) == code]
        expected_path = ('bin/driver/devb-mmcsd-tegra3-devlite' if pc in EMMC_CHECKPOINTS
                         else 'bin/sifsloader')
        if len(owners) != 1 or owners[0][0] != expected_path:
            continue
        path, raw, segments = owners[0]
        label = CHECKPOINTS[pc]
        row = evidence.setdefault(label, dict(pc=hex(pc), path=path, count=0, r0_counts={}, samples=[]))
        row['count'] += 1
        if 0 in registers:
            value = hex(registers[0])
            row['r0_counts'][value] = row['r0_counts'].get(value, 0) + 1
        if label == 'lzo_return' and 2 in registers:
            row['decoded_bytes_total'] = row.get('decoded_bytes_total', 0) + registers[2]
        if len(row['samples']) >= 3:
            continue
        detail = dict(cpu=sample['cpu'], matched_bytes=len(code),
                      registers={f'r{i}': hex(registers[i]) for i in (0, 1, 2, 3, 4, 5, 6, 7, 8, 14)
                                 if i in registers})
        format_reg = 2 if label == 'emmc_diagnostic' else 1
        if label in ('diagnostic', 'emmc_diagnostic') and format_reg in registers:
            # Only strings contained in the verified file, never arbitrary guest pointers.
            value = bytearray()
            for i in range(240):
                byte = file_bytes(raw, segments, registers[format_reg] + i, 1)
                if byte is None or byte == b'\0' or not 32 <= byte[0] <= 126:
                    break
                value.extend(byte)
            if value:
                detail['format'] = value.decode('ascii')
        row['samples'].append(detail)
    commands = re.findall(r'sdhci_send_command CMD(\d+) ARG\[0x([0-9a-fA-F]+)\]', text)
    errors = re.findall(r'sdhci_error ([^\n]{1,240})', text)
    return dict(checkpoints=evidence,
                sdmmc_command_count=len(commands),
                sdmmc_commands=[dict(command=int(cmd), argument=hex(int(arg, 16))) for cmd, arg in commands[:32]],
                sdmmc_errors=errors[:16],
                caution='Milestone registers are pre-instruction state. A mount return applies only to that call; it does not prove later mounts or device readiness.')
