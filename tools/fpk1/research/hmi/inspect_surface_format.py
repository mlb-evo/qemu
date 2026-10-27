"""Prove DC byte order by executing the original FPK1 libnvdisp selector.

Requires the configm-venv (Unicorn) and libnvdisp extracted from Stage1.
No firmware instructions are patched. Controller/window/memory and return
boundaries are synthetic; the selector's emitted register writes are real.
"""
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from qnx_elf_disasm import Elf
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR


def main():
    elf = Elf(REPO / 'build_fpk1/research-artifacts/stage2/STAGE1/lib/libnvdisp.so')
    rows = []
    for fmt, expected_swap in ((0x20168815, 2), (0x20105315, 0)):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(0, 0x30000)
        for kind, offset, address, _, size, *_ in elf.ph:
            if kind == 1:
                cpu.mem_write(address, elf.data[offset:offset + size])
        cpu.mem_map(0x300000, 0x120000)

        def word(address, value):
            cpu.mem_write(address, struct.pack('<I', value))

        word(0x300008, 0x330000)
        word(0x330018, 0x100)  # original selector's direct register-write path
        word(0x301274, 0x340000)
        word(0x34004c, 0x350000)
        word(0x320008, fmt)
        for register, value in ((UC_ARM_REG_R0, 0x300000), (UC_ARM_REG_R1, 0x310000),
                                (UC_ARM_REG_R2, 0x320000), (UC_ARM_REG_SP, 0x41fff0),
                                (UC_ARM_REG_LR, 0x400000)):
            cpu.reg_write(register, value)
        cpu.emu_start(0x7738, 0x400000, count=10000)
        end, = struct.unpack('<I', cpu.mem_read(0x34004c, 4))
        writes = dict(struct.iter_unpack('<II', cpu.mem_read(0x350000, end - 0x350000)))
        assert cpu.reg_read(UC_ARM_REG_R0) == 1
        assert writes[0x27030001] == 13
        assert writes[0x27010001] == expected_swap
        rows.append(dict(surface_format=hex(fmt), color_depth=13, byte_swap=expected_swap,
                         original_function='libnvdisp.so:0x7738'))
    out = REPO / 'build_fpk1/research-artifacts/scanout-pixel-check/surface-format-proof.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2) + '\n')
    print('PASS: original driver selects depth 13 / no byte swap for the bridge RGBA format')


if __name__ == '__main__':
    main()
