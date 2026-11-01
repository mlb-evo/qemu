"""Local Navigation availability cross-references; outputs stay private.

Run with Capstone on PYTHONPATH. No firmware or QEMU sources are modified.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import re
from pathlib import Path
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from qnx_elf_disasm import Elf, instructions, annotate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', choices=('gss_ipc', 'gtf2'))
    parser.add_argument('needles', nargs='+')
    parser.add_argument('--before', type=int, default=160)
    parser.add_argument('--after', type=int, default=240)
    parser.add_argument('--name', default='xrefs')
    args = parser.parse_args()
    elf = Elf(REPO / 'build_fpk1/research-artifacts/wheel' / args.binary)
    refs = []
    for ins in instructions(elf):
        m = re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]', ins.op_str)
        if ins.mnemonic == 'ldr' and m:
            value = elf.word(ins.address + 8 + int(m[1], 0))
            s = elf.cstr(value) if value is not None else None
            if s and any(n in s for n in args.needles):
                refs.append((ins.address, s))
    out = REPO / 'build_fpk1/research-artifacts/navigation'
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'{args.binary}-{args.name}.txt'
    with path.open('w') as f:
        for address, s in refs:
            print(f'{address:#x}: {s}')
            f.write(f'\n{address:#x}: {s}\n')
            for ins in instructions(elf, address - args.before, address + args.after):
                f.write(annotate(elf, ins) + '\n')
    print(path)


if __name__ == '__main__':
    main()
