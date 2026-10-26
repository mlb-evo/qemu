#!/usr/bin/env python3
"""ARM disassembly of QNX ELF files without section headers (research aid).

QNX executables and libraries in the FPK1 images are stripped of sections, so
binutils cannot show symbols. This reads PT_DYNAMIC directly, names PLT stubs
from DT_JMPREL relocations, and annotates `bl` targets, PC-relative literals
and C strings they point at. Modes:

  calls FILE NAME...      list call sites of the named imports
  dis FILE START END      disassemble [START, END) (hex virtual addresses)
  syms FILE [NAME...]     list defined dynamic symbols
"""
import re
import struct
import sys

import capstone


class Elf:
    def __init__(self, path):
        self.data = d = open(path, 'rb').read()
        phoff, = struct.unpack_from('<I', d, 28)
        count, = struct.unpack_from('<H', d, 44)
        self.ph = [struct.unpack_from('<8I', d, phoff + 32 * i) for i in range(count)]
        dyn = next(p for p in self.ph if p[0] == 2)
        self.tags = {}
        for i in range(0, dyn[4], 8):
            tag, value = struct.unpack_from('<II', d, dyn[1] + i)
            if tag == 0:
                break
            self.tags.setdefault(tag, value)
        self.strtab, self.symtab = self.off(self.tags[5]), self.off(self.tags[6])
        self.plt = self._plt()

    def off(self, va):
        for kind, offset, vaddr, _, filesz, *_ in self.ph:
            if kind == 1 and vaddr <= va < vaddr + filesz:
                return offset + va - vaddr
        return None

    def word(self, va):
        o = self.off(va)
        return None if o is None or o + 4 > len(self.data) else struct.unpack_from('<I', self.data, o)[0]

    def cstr(self, va):
        o = self.off(va)
        if o is None:
            return None
        end = self.data.find(b'\0', o)
        text = self.data[o:end]
        if 3 <= len(text) < 160 and all(32 <= c < 127 or c in (9, 10) for c in text):
            return text.decode()
        return None

    def symname(self, index):
        name, = struct.unpack_from('<I', self.data, self.symtab + 16 * index)
        return self.data[self.strtab + name:self.data.index(b'\0', self.strtab + name)].decode()

    def symbols(self):
        nchain, = struct.unpack_from('<I', self.data, self.off(self.tags[4]) + 4)
        for i in range(1, nchain):
            _, value, size, _, _, shndx = struct.unpack_from('<IIIBBH', self.data, self.symtab + 16 * i)
            if shndx:
                yield self.symname(i), value, size

    def text(self):
        seg = next(p for p in self.ph if p[0] == 1 and p[6] & 1)
        return seg[2], self.data[seg[1]:seg[1] + seg[4]]

    def _plt(self):
        got = {}
        rel = self.off(self.tags.get(23, 0)) if 23 in self.tags else None
        for i in range(0, self.tags.get(2, 0), 8):
            r_offset, info = struct.unpack_from('<II', self.data, rel + i)
            got[r_offset] = self.symname(info >> 8)
        base, code = self.text()
        plt = {}
        # Stub: add ip, pc, #a; add ip, ip, #b; ldr pc, [ip, #c]! (immediates decoded
        # from the encoding: capstone prints ARM rotations as a second '#n').
        for at in range(0, len(code) - 11, 4):
            w0, w1, w2 = struct.unpack_from('<3I', code, at)
            if (w0 & 0xfffff000) == 0xe28fc000 and (w1 & 0xfffff000) == 0xe28cc000 \
                    and (w2 & 0xfffff000) in (0xe5bcf000, 0xe53cf000):
                off = w2 & 0xfff if w2 & (1 << 23) else -(w2 & 0xfff)
                target = (base + at + 8 + rot_imm(w0) + rot_imm(w1) + off) & 0xffffffff
                if target in got:
                    plt[base + at] = got[target]
        return plt


def rot_imm(word):
    value, rotate = word & 0xff, ((word >> 8) & 0xf) * 2
    return ((value >> rotate) | (value << (32 - rotate))) & 0xffffffff if rotate else value


def instructions(elf, start=None, end=None):
    base, code = elf.text()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    md.skipdata = True
    lo = 0 if start is None else start - base
    hi = len(code) if end is None else end - base
    return md.disasm(code[lo:hi], base + lo)


def annotate(elf, ins):
    text = f'{ins.address:#x}: {ins.mnemonic} {ins.op_str}'
    m = re.match(r'#(0x[0-9a-f]+)', ins.op_str)
    if ins.mnemonic in ('bl', 'blx', 'b') and m and int(m.group(1), 16) in elf.plt:
        text += f'  <{elf.plt[int(m.group(1), 16)]}>'
    m = re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]', ins.op_str)
    if m and ins.mnemonic.startswith('ldr'):
        value = elf.word(ins.address + 8 + int(m.group(1), 0))
        if value is not None:
            s = elf.cstr(value)
            text += f'  ; ={value:#x}' + (f' "{s}"' if s else '')
    return text


def main():
    mode, path = sys.argv[1], sys.argv[2]
    elf = Elf(path)
    if mode == 'calls':
        wanted = set(sys.argv[3:])
        for ins in instructions(elf):
            m = re.match(r'#(0x[0-9a-f]+)', ins.op_str)
            if ins.mnemonic in ('bl', 'blx') and m and elf.plt.get(int(m.group(1), 16)) in wanted:
                print(hex(ins.address), elf.plt[int(m.group(1), 16)])
    elif mode == 'dis':
        for ins in instructions(elf, int(sys.argv[3], 16), int(sys.argv[4], 16)):
            print(annotate(elf, ins))
    elif mode == 'syms':
        wanted = set(sys.argv[3:])
        for name, value, size in elf.symbols():
            if not wanted or name in wanted:
                print(hex(value), hex(size), name)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
