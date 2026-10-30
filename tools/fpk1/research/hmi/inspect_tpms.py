"""Recheck original Q7 0378 TPMS descriptors; keep evidence in private artifacts.

Requires Capstone on PYTHONPATH and the extracted wheel/gss_ipc and wheel/gtf2.
This checks metadata and records original readers; it does not certify rendering.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from qnx_elf_disasm import Elf, instructions, annotate
from hmi.tpms import DEFAULT, properties


def main():
    directory = REPO / 'build_fpk1/research-artifacts'
    gss = Elf(directory / 'wheel/gss_ipc')
    gtf = Elf(directory / 'wheel/gtf2')
    values = properties(DEFAULT)
    assert gss.word(0x1a82d0) == 7
    at = gss.off(0x1a81f8)
    assert gss.data[at:at + 6] == values[2]
    rows = {}
    for address in range(0x19a9e4, 0x19acb4, 40):
        function = gss.word(address + 4)
        rows[function] = dict(size=gss.word(address + 8) & 0xffff,
                              cid=gss.word(address + 32))
    for function in (2, 3, 15, 16, 17, 18, 19):
        assert rows[function] == dict(size=len(values[function]), cid=7)
    # Original RDK activation uses bit 3, separate from OnlineFunctions bit 22.
    assert gtf.word(0x157670) == 0xe3833008  # orr r3, r3, #8
    # The state reader uses ten 4-bit fields, followed by one byte.
    calls = [i.op_str for i in instructions(gtf, 0x798bc0, 0x798cbc) if i.mnemonic == 'bl']
    assert calls.count('#0x76bf6c') == 10 and calls.count('#0x76bf44') == 1
    out = directory / 'tpms'
    out.mkdir(parents=True, exist_ok=True)
    report = dict(passed=True, fsg=7, can_cid=7, activation_mask=8,
                  descriptors=rows,
                  sha256={name: hashlib.sha256(elf.data).hexdigest()
                          for name, elf in (('gss_ipc', gss), ('gtf2', gtf))},
                  scope='Original descriptor/static reader checks; guest rendering not checked')
    (out / 'metadata-check.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'readers.txt').write_text('\n\n'.join(
        '\n'.join(annotate(gtf, i) for i in instructions(gtf, lo, hi))
        for lo, hi in ((0x798bc0, 0x798cbc), (0x79851c, 0x7985b8),
                       (0x798334, 0x7983d0), (0x79814c, 0x7981e8),
                       (0x188638, 0x1887d0), (0x188804, 0x188860),
                       (0x188a4c, 0x188bc4), (0x157650, 0x157690))) + '\n')
    print(out / 'metadata-check.json')


if __name__ == '__main__':
    main()
