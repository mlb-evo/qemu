"""Recover local assist controls by executing original Q7 0378 ARM code.

Needs capstone/unicorn and original gss_ipc extracted by inspect_mfl.py.
All generated reports stay under build_fpk1/research-artifacts/driver-assist/.
"""
import sys
sys.dont_write_bytecode = True
import json
import hashlib
import random
import re
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from qnx_elf_disasm import Elf, instructions
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

NAMES = ('ACC_KBI', 'TelltaleAALA_Display', 'ACC_HMI_Display', 'ACC_HMI_Ring',
         'ACC_02', 'ACC_12', 'ACC_14', 'ACC_13_HMIStatus', 'LDW_02', 'TSK_07',
         'HMI_C_NightVision_Parameters', 'HMI_C_NightVision_Display', 'TelltaleHMI_Display',
         'VZE_01', 'VZE_Timeout', 'ZPM_HMI_Info')
BASE, WIRE, STATE, STACK, STOP = 0x4000000, 0x4000000, 0x4001000, 0x40f0000, 0x40ff000


def immediate(elf, ins, regs):
    m = re.fullmatch(r'(r[01]), (r[01])', ins.op_str)
    if ins.mnemonic == 'mov' and m and m[2] in regs:
        return m[1], regs[m[2]]
    m = re.fullmatch(r'(r[01]), #(0x[0-9a-f]+|\d+)', ins.op_str)
    if ins.mnemonic in ('mov', 'movw') and m:
        return m[1], int(m[2], 0)
    m = re.fullmatch(r'(r[01]), \[pc, #(-?0x[0-9a-f]+|-?\d+)\]', ins.op_str)
    if ins.mnemonic == 'ldr' and m:
        return m[1], elf.word(ins.address + 8 + int(m[2], 0))
    return None


class Oracle:
    def __init__(self, elf):
        self.elf = elf
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        loads = [p for p in elf.ph if p[0] == 1]
        lo = min(p[2] for p in loads) & ~4095
        hi = (max(p[2] + p[5] for p in loads) + 4095) & ~4095
        self.cpu.mem_map(lo, hi - lo)
        for p in loads:
            self.cpu.mem_write(p[2], elf.data[p[1]:p[1] + p[4]])
        self.cpu.mem_map(BASE, 0x100000)
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)
        self.fields = {}
        self.label = None

    def hook(self, cpu, address, size, user):
        if address == 0x1096e8:
            label = self.elf.cstr(cpu.reg_read(UC_ARM_REG_R1))
            if label and label.endswith(' = '):
                self.label = label[:-3]
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        elif address == 0x13871c or address in self.elf.plt:
            if self.label:
                self.fields[self.label] = cpu.reg_read(UC_ARM_REG_R1)
                self.label = None
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def call(self, address, r0, r1):
        self.cpu.reg_write(UC_ARM_REG_SP, STACK)
        self.cpu.reg_write(UC_ARM_REG_LR, STOP)
        self.cpu.reg_write(UC_ARM_REG_R0, r0)
        self.cpu.reg_write(UC_ARM_REG_R1, r1)
        self.cpu.emu_start(address, STOP, count=30000)
        if self.cpu.reg_read(UC_ARM_REG_PC) != STOP:
            raise ValueError(f'Original function did not return: {address:#x}')

    def decode(self, unpacker, formatter, wire):
        self.cpu.mem_write(WIRE, wire)
        self.cpu.mem_write(STATE, bytes(512))
        self.call(unpacker, STATE, WIRE)
        self.fields, self.label = {}, None
        self.call(formatter, STATE + 1024, STATE)
        return dict(self.fields)


def main():
    elf = Elf(REPO / 'build_fpk1/research-artifacts/wheel/gss_ipc')
    out = REPO / 'build_fpk1/research-artifacts/driver-assist'
    out.mkdir(parents=True, exist_ok=True)
    code = list(instructions(elf))
    refs = {}
    for ins in code:
        m = re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]', ins.op_str)
        if ins.mnemonic == 'ldr' and m:
            value = elf.word(ins.address + 8 + int(m[1], 0))
            s = elf.cstr(value) if value is not None else None
            if s:
                refs.setdefault(s, []).append(ins.address)
    callbacks = {}
    for data_id in range(0xbb8):
        at = 0x1abdf0 + data_id * 20
        if elf.word(at) != data_id:
            continue
        length, callback = elf.word(at + 4), elf.word(at + 16)
        if not callback or not 0 < length <= 128:
            continue
        regs, unpacker = {}, None
        for ins in instructions(elf, callback, callback + 112):
            item = immediate(elf, ins, regs)
            if item:
                regs[item[0]] = item[1]
            if ins.mnemonic == 'bl':
                target = int(ins.op_str[1:], 0)
                if target == 0x162620:
                    callbacks[regs.get('r0'), regs.get('r1')] = (data_id, length, unpacker)
                    break
                unpacker = target
            if ins.mnemonic == 'pop' and 'pc' in ins.op_str:
                break
    oracle = Oracle(elf)
    catalog = []
    for name in NAMES:
        read_refs = [a for s, addrs in refs.items() if s.startswith('Rte_Read_')
                     and s.endswith(' returned %d') and ('_' + name + ' returned') in s
                     for a in addrs]
        # ACC_KBI's struct name is ACC_KBI_Status; AALA uses AALA_Lamps.
        if not read_refs:
            suffix = {'ACC_KBI': 'ACC_KBI_Status', 'TelltaleAALA_Display': 'AALA_Lamps',
                      'HMI_C_NightVision_Parameters': 'NightVision_Parameters',
                      'HMI_C_NightVision_Display': 'NightVision_Display',
                      'VZE_Timeout': 'VZE_timeout'}.get(name, name)
            read_refs = [a for s, addrs in refs.items() if s.startswith('Rte_Read_')
                         and s.endswith('_' + suffix + ' returned %d') for a in addrs]
        if not read_refs:
            raise ValueError(f'No reader for {name}')
        regs, component = {}, None
        for ins in instructions(elf, read_refs[-1] - 160, read_refs[-1]):
            item = immediate(elf, ins, regs)
            if item:
                regs[item[0]] = item[1]
            if ins.mnemonic == 'bl' and ins.op_str == '#0x162578':
                component = (regs.get('r0'), regs.get('r1'))
        data_id, length, unpacker = callbacks[component]
        at = refs[name + '(incoming data='][0]
        calls = [int(i.op_str[1:], 0) for i in instructions(elf, at + 4, at + 28) if i.mnemonic == 'bl']
        formatter = calls[1] if len(calls) > 1 else None
        if name == 'ACC_KBI':
            fields = [dict(name='available', bits=[0])]
        else:
            zero = oracle.decode(unpacker, formatter, bytes(length))
            mapping = {field: {} for field in zero}
            for bit in range(length * 8):
                wire = (1 << bit).to_bytes(length, 'little')
                values = oracle.decode(unpacker, formatter, wire)
                for field, value in values.items():
                    signed = re.search(r'sint(8|16|32)', field)
                    if signed:
                        value &= (1 << int(signed[1])) - 1
                    delta = value ^ zero[field]
                    if delta:
                        if delta & (delta - 1):
                            raise ValueError(f'Nonlinear field: {name}.{field}')
                        mapping[field][delta.bit_length() - 1] = bit
            fields = []
            for field, positions in mapping.items():
                if not positions or re.search(r'reserved|unused', field, re.I):
                    continue
                if set(positions) != set(range(max(positions) + 1)):
                    raise ValueError(f'Incomplete mapping: {name}.{field}')
                fields.append(dict(name=field, bits=[positions[n] for n in range(len(positions))],
                                   signed=bool(re.search(r'sint(8|16|32)', field))))
        row = dict(name=name, data_id=data_id, size=length, unpacker=unpacker,
                   formatter=formatter, component=component, fields=fields)
        catalog.append(row)
        print(name, hex(data_id), length, len(fields), flush=True)
    (out / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')
    # Validate the runtime encoder, not merely the extraction algorithm: each
    # random state is packed by the UI's module, unpacked and formatted by the
    # original ARM routines, then compared field by field (including signs).
    from research.hmi.driver_assist import pack
    from research.hmi.assist_catalog import SIGNALS
    rng = random.Random(378)
    checks = 0
    for row in catalog:
        name = row['name']
        expected_fields = tuple((f['name'], tuple(f['bits']), f.get('signed', False)) for f in row['fields'])
        assert SIGNALS[name] == (row['data_id'], row['size'], expected_fields)
        for case in range(34):
            values = {}
            for f in row['fields']:
                width = len(f['bits'])
                lo = -(1 << (width - 1)) if f.get('signed') else 0
                hi = (1 << (width - int(f.get('signed', False)))) - 1
                values[f['name']] = lo if case == 0 else (hi if case == 1 else rng.randint(lo, hi))
            wire = pack(name, values)
            if name == 'ACC_KBI':
                oracle.cpu.mem_write(WIRE, wire)
                oracle.call(row['unpacker'], STATE, WIRE)
                assert oracle.cpu.mem_read(STATE, 1)[0] & 1 == values['available']
            else:
                actual = oracle.decode(row['unpacker'], row['formatter'], wire)
                for f in row['fields']:
                    mask = (1 << len(f['bits'])) - 1
                    assert actual[f['name']] & mask == values[f['name']] & mask, (name, f, values, actual)
            checks += 1
    report = dict(sha256=hashlib.sha256(elf.data).hexdigest(), signals=len(catalog),
                  fields=sum(len(row['fields']) for row in catalog),
                  original_arm_roundtrips=checks, passed=True)
    (out / 'oracle-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report)


if __name__ == '__main__':
    main()
