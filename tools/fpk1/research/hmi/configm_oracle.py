"""Execute the original Q7 0378 long-coding decoder and l4c packers locally.

Requires unicorn. No MCU startup or peripherals are emulated. Rte_Write is
intercepted at its boundary; all bit extraction and wire packing is firmware
code. Inputs are the 20 coding bytes, with no user-settings override.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
IMAGE = REPO / 'build_fpk1/research-artifacts/configm/kss.bin'
SHA256 = '9a5261a593ddf4dd322413c2011647e735aca65afc225aa8adf96d4df74776d2'


class Oracle:
    def __init__(self):
        data = IMAGE.read_bytes()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError('This oracle requires the original Q7 0378 KSS image')
        self.data = data
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for base, size in ((0, 0x20000), (0x1000000, 0x100000), (0x1a00000, 0x100000), (0x2000000, 0x10000)):
            self.cpu.mem_map(base, size)
        self.cpu.mem_write(0x1000000, data)
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)
        self.values = {}

    def word(self, address):
        return struct.unpack_from('<I', self.data, address - 0x1000000)[0]

    def hook(self, cpu, address, size, _):
        if address == 0x1005bf4:  # Rte_Write(component, element, value)
            component = cpu.reg_read(UC_ARM_REG_R0)
            element = cpu.reg_read(UC_ARM_REG_R1)
            pointer = cpu.reg_read(UC_ARM_REG_R2)
            descriptor = self.word(0x10cd568 + component * 8) + element * 12
            length = self.word(descriptor + 8) & 0xffff
            self.values[component, element] = bytes(cpu.mem_read(pointer, length))
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def call(self, address, r0=0, r1=0):
        cpu = self.cpu
        cpu.reg_write(UC_ARM_REG_R0, r0)
        cpu.reg_write(UC_ARM_REG_R1, r1)
        cpu.reg_write(UC_ARM_REG_SP, 0x200f000)
        cpu.reg_write(UC_ARM_REG_LR, 0x2000001)
        cpu.emu_start(address | 1, 0x2000000, count=100000)
        if cpu.reg_read(UC_ARM_REG_PC) != 0x2000000:
            raise RuntimeError('Firmware routine exceeded the instruction limit')

    def decode(self, coding):
        if len(coding) != 20:
            raise ValueError('Long coding must contain exactly 20 bytes')
        self.values = {}
        self.cpu.mem_write(0xb400, bytes(coding) + bytes(4))
        self.cpu.mem_write(0xc308, struct.pack('<I', 0xb400))
        self.cpu.mem_write(0xb418, bytes(24))  # no persisted user overrides
        self.cpu.mem_write(0x2000000, bytes(0x10000))
        self.call(0x1086094)
        result = {}
        for element in range(7):
            data_id = 0x127 + element
            value = self.values[0xce, element]
            entry = 0x10cf108 + data_id * 20
            length, packer = self.word(entry + 4), self.word(entry + 12)
            self.cpu.mem_write(0x2000100, value)
            self.cpu.mem_write(0x2000200, bytes(64))
            self.call(packer, 0x2000100, 0x2000200)
            result[data_id] = bytes(self.cpu.mem_read(0x2000200, length))
        # CodedLanguage is not on the wire in this firmware version.
        return result


if __name__ == '__main__':
    oracle = Oracle()
    if sys.argv[1] == '--derive':
        baseline = oracle.decode(bytes(20))
        assert not any(any(v) for v in baseline.values())
        mapping = {key: [-1] * (len(value) * 8) for key, value in baseline.items()}
        for bit in range(160):
            coding = (1 << bit).to_bytes(20, 'little')
            for key, value in oracle.decode(coding).items():
                for outbit in range(len(value) * 8):
                    if value[outbit // 8] >> (outbit % 8) & 1:
                        assert mapping[key][outbit] == -1
                        mapping[key][outbit] = bit
        for key, bits in mapping.items():
            print(f'{key:#05x}: {tuple(bits)},')
    else:
        for data_id, value in oracle.decode(bytes.fromhex(sys.argv[1])).items():
            print(f'{data_id:#05x}: {value.hex()}')
