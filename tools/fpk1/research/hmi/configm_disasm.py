"""Disassemble the locally extracted KSS image (Thumb); research only."""
import sys
sys.dont_write_bytecode = True
import struct
from pathlib import Path
import capstone

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
BASE = 0x1000000
data = (REPO / 'build_fpk1/research-artifacts/configm/kss.bin').read_bytes()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.skipdata = True
start, end = (int(a, 16) for a in sys.argv[1:])
for ins in md.disasm(data[start - BASE:end - BASE], start):
    text = f'{ins.address:#x}: {ins.mnemonic} {ins.op_str}'
    if ins.mnemonic == 'ldr' and '[pc, #' in ins.op_str:
        off = int(ins.op_str.split('#')[1].split(']')[0], 0)
        at = ((ins.address + 4) & ~3) + off - BASE
        value, = struct.unpack_from('<I', data, at)
        text += f' ; ={value:#x}'
    print(text)
