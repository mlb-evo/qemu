"""Local source provenance and null-shortcut experiment in original firmware.

Requires the configm-venv runtime and extracted KSS/libeal images. Outputs
metadata under build_fpk1/research-artifacts/resource-audit/ only. No VM edits.
"""
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path
import struct

from configm_oracle import Oracle, REPO
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from qnx_elf_disasm import Elf
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR,
                              UC_ARM_REG_PC)


def source_metadata():
    oracle = Oracle()
    descriptor = 0x10dc44c + 0x39 * 24
    words = [oracle.word(descriptor + off) for off in range(0, 24, 4)]
    storage_id = words[4] & 0xffff
    size = words[4] >> 16
    matches = []
    for index in range(0xe5):
        at = 0x10df8f4 + index * 8
        block, length, auxiliary = struct.unpack_from('<HHI', oracle.data, at - 0x1000000)
        if block == storage_id:
            matches.append(dict(index=index, address=hex(at), storage_id=hex(block),
                                size=length, auxiliary=auxiliary))
    assert size == len(oracle.default_internal()) == 16
    assert len(matches) == 1 and matches[0]['size'] == size
    # Execute the original default-restoration function against a poisoned RAM
    # block. This is the explicit restoration path, not a full NvM boot model.
    oracle.cpu.mem_write(0xb430, bytes([0xa5]) * size)
    state = bytearray(0x40)
    struct.pack_into('<I', state, 0, descriptor)
    struct.pack_into('<I', state, 8, 0xb430)
    oracle.cpu.mem_write(0xde14, bytes(state))
    oracle.call(0x109aee8)
    restored = bytes(oracle.cpu.mem_read(0xb430, size))
    assert restored == oracle.default_internal()
    return dict(nvm_block='0x39', descriptor=hex(descriptor),
                descriptor_words=[hex(w) for w in words], ram=hex(words[0]),
                rom_fallback_address=hex(words[1]), rom_fallback=restored.hex(),
                storage_table=matches, restoration_routine='0x109aee8',
                note='Explicit ROM restoration verified; persisted device block not available')


def shortcut_records():
    rows = []
    for path in sorted((REPO / 'build_fpk1/research-artifacts/stage2/STAGE2.2/data/gtf').glob('*TabBar.kzb')):
        data = path.read_bytes()
        end = 0x3c + struct.unpack_from('>I', data, 0x34)[0]
        for pos in range(0x3c, end - 18):
            offset, size, kind, flags, length = struct.unpack_from('>IIIIH', data, pos)
            name = data[pos + 18:pos + 18 + length]
            if (kind != 5 or flags != 0 or size != 4 or
                    not end <= offset <= len(data) - 9 or
                    name not in (b'TabBar_Content_RootLayer', b'TabBar_Content_TabEntryLayer')):
                continue
            # Original OpenFileWithReferences consumes the count and byte
            # reference-list header; the U32 shortcut target follows at +5.
            count = struct.unpack_from('<I', data, offset)[0]
            reference = struct.unpack_from('<I', data, offset + 5)[0]
            rows.append(dict(file=path.name, name=name.decode(), kind=kind,
                             offset=hex(offset), reference_count=count,
                             target_reference=reference,
                             raw_header_and_reference=data[offset:offset + 9].hex()))
    assert len(rows) == 4
    return rows


def original_null_shortcut():
    elf = Elf(REPO / 'build_fpk1/research-artifacts/stage2/STAGE2.1/lib/libeal.so')
    symbols = {name: address for name, address, _ in elf.symbols()}
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0, 0x400000)
    cpu.mem_map(0x2000000, 0x10000)
    for kind, offset, address, _, size, *_ in elf.ph:
        if kind == 1:
            cpu.mem_write(address, elf.data[offset:offset + size])
    messages = []

    def hook(cpu, address, size, _):
        name = elf.plt.get(address)
        if not name:
            return
        result = 0
        if name == 'kzcMemoryGetManager':
            result = 0x2000200
        elif name == 'kzcHashMapStringGetString':
            # Controlled fixture: the shortcut exists and its target is NULL.
            cpu.mem_write(cpu.reg_read(UC_ARM_REG_R2), bytes(4))
            result = 1
        elif name == 'kzsExceptionLog_private':
            messages.append(elf.cstr(cpu.reg_read(UC_ARM_REG_R0)))
        elif name == 'kzsExceptionOccurred_private':
            result = cpu.reg_read(UC_ARM_REG_R0)
        elif name in symbols:
            cpu.reg_write(UC_ARM_REG_PC, symbols[name])
            return
        else:
            raise RuntimeError('Unexpected unstubbed import: ' + name)
        cpu.reg_write(UC_ARM_REG_R0, result)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.mem_write(0x2001000, b'TabBar_Content_RootLayer\0')
    cpu.reg_write(UC_ARM_REG_R0, 0x2000300)
    cpu.reg_write(UC_ARM_REG_R1, 0x2001000)
    cpu.reg_write(UC_ARM_REG_R2, 0x2000400)
    cpu.reg_write(UC_ARM_REG_SP, 0x200f000)
    cpu.reg_write(UC_ARM_REG_LR, 0x2000000)
    cpu.emu_start(symbols['kzuBinaryDirectoryGetFile'], 0x2000000, count=10000)
    result = struct.unpack('<i', struct.pack('<I', cpu.reg_read(UC_ARM_REG_R0)))[0]
    assert result == -30101
    assert messages == ['Trying to get binary file from shortcut with missing target']
    return dict(routine=hex(symbols['kzuBinaryDirectoryGetFile']),
                fixture='existing shortcut with NULL target; allocator and hash lookup stubbed',
                result=result, messages=messages)


def original_design_source():
    oracle = Oracle()
    descriptor = 0x10dc44c + 0x4b * 24
    words = [oracle.word(descriptor + off) for off in range(0, 24, 4)]
    size = words[4] >> 16
    default = oracle.data[words[1] - 0x1000000:words[1] - 0x1000000 + size]
    assert words[0] == 0xb0f4 and size == 19
    allowed = True

    def hook(cpu, address, size, _):
        if address in (0x1078404, 0x1078408, 0x104f7f2, 0x104ef54):
            result = {0x1078404: 0x2004000, 0x1078408: 0x2004100,
                      0x104f7f2: int(allowed), 0x104ef54: 0}[address]
            cpu.reg_write(UC_ARM_REG_R0, result)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    oracle.cpu.hook_add(UC_HOOK_CODE, hook)
    cases = []
    for mask, saved, allowed in ((0, 1, True), (3, 1, True), (3, 1, False), (3, 0, True)):
        internal = bytearray(oracle.default_internal())
        internal[9] = mask
        persisted = bytearray(default)
        persisted[18] = saved
        oracle.cpu.mem_write(0xb430, bytes(internal))
        oracle.cpu.mem_write(0xb0f4, bytes(persisted))
        oracle.cpu.mem_write(0x2004000, bytes(0x200))
        oracle.values = {}
        oracle.call(0x1050986)
        oracle.call(0x10509f0)
        value = oracle.values[0x178, 0]
        wire = oracle.pack(0x3cd, value)
        expected = saved if mask and allowed else 0
        assert wire == bytes([expected]) * 4
        cases.append(dict(internal_byte9=mask, persisted_byte18=saved,
                          availability_gate_stub=allowed, design_message=wire.hex()))
    return dict(nvm_block='0x4b', ram=hex(words[0]), size=size,
                storage_id=hex(words[4] & 0xffff), rom_fallback=default.hex(),
                selected_design_byte=18, rom_selected_design=default[18],
                availability_mask_source='NvM 0x39 byte 9',
                producer='0x10509f0', rte_component='0x178', l4c_id='0x3cd',
                gss_rte_component='0x7e', hmi_datapool='0x200017d',
                hmi_variant_mapping={'0': '0x0 (ordinary)', '1': '0x100 (Sport)'},
                note='Manager getters, availability gate and final engine tick stubbed; original selection and packing executed',
                cases=cases)


def original_design_diagnostic():
    oracle = Oracle()

    def hook(cpu, address, size, _):
        if address == 0x1005e00:
            assert cpu.reg_read(UC_ARM_REG_R0) == 0xee
            assert cpu.reg_read(UC_ARM_REG_R1) == 0
            cpu.mem_write(cpu.reg_read(UC_ARM_REG_R2), struct.pack('<HHI', 0x0919, 0, 0x2005000))
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    oracle.cpu.hook_add(UC_HOOK_CODE, hook)
    cases = []
    for saved in (0, 1):
        oracle.cpu.mem_write(0xb106, bytes([saved]))  # NvM 0x4b + 18
        oracle.cpu.mem_write(0x2005000, bytes(16))
        oracle.call(0x10508b4)
        reply = bytes(oracle.cpu.mem_read(0x2005000, 5))
        assert reply == bytes([4, 0x62, 0x09, 0x19, saved])
        cases.append(dict(saved_design=saved, application_reply=reply.hex(),
                          uds_payload=reply[1:].hex()))
    return dict(handler='0x10508b4', request='220919',
                reads='NvM 0x4b byte 18', cases=cases,
                note='Original local handler verified; no request sent to hardware')


def main():
    report = dict(internal_source=source_metadata(), design_source=original_design_source(), shortcuts=shortcut_records(),
                  design_diagnostic=original_design_diagnostic(),
                  original_kanzi_null_shortcut=original_null_shortcut())
    out = REPO / 'build_fpk1/research-artifacts/resource-audit/config-source-proof.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
