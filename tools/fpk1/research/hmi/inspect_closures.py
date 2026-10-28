"""Record original Q7 0378 closure descriptor/unpacker and named bit fields.

Run inspect_mfl.py first to extract original gss_ipc. Requires capstone.
Reports and disassembly stay under build_fpk1/research-artifacts/closures/.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import struct
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from qnx_elf_disasm import Elf, annotate, instructions
from decompress_kss import extract


def main():
    source = REPO / 'build_fpk1/research-artifacts/wheel/gss_ipc'
    elf = Elf(source)
    out = REPO / 'build_fpk1/research-artifacts/closures'
    out.mkdir(parents=True, exist_ok=True)
    descriptor = [elf.word(0x1abf30 + 4 * i) for i in range(5)]
    assert descriptor == [0x10, 2, 0, 0x1643a8, 0x169bb0]
    active = [elf.word(0x1ae118 + 4 * i) for i in range(5)]
    assert active == [0x1c2, 1, 0, 0x1643a8, 0x16908c]
    report = dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  descriptor=[hex(v) for v in descriptor], rte_component='0x3c', rte_element=0,
                  active_descriptor=[hex(v) for v in active], active_rte_element=1,
                  active_gtf2_dpid='0x02000198',
                  wire_bytes=2, wire_order='unchanged by unpacker 0x16728c',
                  byte0_bits=['car_frontLeftDoor_b', 'car_frontRightDoor_b',
                              'car_rearLeftDoor_b', 'car_rearRightDoor_b',
                              'car_boot_b', 'car_bonnet_b', 'car_rearWindow_b', 'car_spareWheel_b'],
                  byte1='bit 0: car_tankDoor_b; bits 1..7: unused',
                  ui_scope='first six bits only; all other bits zero')
    (out / 'wire.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'disassembly.txt').write_text('\n\n'.join(
        '\n'.join(annotate(elf, i) for i in instructions(elf, start, end))
        for start, end in ((0x16728c, 0x1672f8), (0x169bb0, 0x169bdc),
                           (0x13b73c, 0x13b878), (0x131480, 0x131504),
                           (0x16908c, 0x1690b8), (0x131590, 0x1315a4))) + '\n')
    gtf = Elf(REPO / 'build_fpk1/research-artifacts/wheel/gtf2')
    (out / 'activation-disassembly.txt').write_text('\n\n'.join(
        '\n'.join(annotate(gtf, i) for i in instructions(gtf, start, end))
        for start, end in ((0x6956fc, 0x695724), (0x2182fc, 0x218344),
                           (0x1b9020, 0x1b9108), (0x6208dc, 0x620a00))) + '\n')
    kss, metadata = extract(REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip')
    descriptor = struct.unpack_from('<6I', kss, 0x10dcb54 - 0x1000000)
    assert descriptor[:2] == (0xb0f4, 0x10f37b4)
    assert descriptor[4] >> 16 == 19
    default = kss[0x10f37b4 - 0x1000000:0x10f37b4 - 0x1000000 + 19]
    assert default[18] == 0
    (out / 'design-rom.json').write_text(json.dumps(dict(
        kss_sha256=metadata['sha256'], block='0x4b',
        descriptor=[hex(v) for v in descriptor], rom=default.hex(),
        selected_design_byte=default[18], producer='0x10509f0'), indent=2) + '\n')
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    (out / 'design-producer.txt').write_text('\n'.join(
        f'{i.address:#x}: {i.mnemonic} {i.op_str}' for i in md.disasm(
            kss[0x509f0:0x50a90], 0x10509f0)) + '\n')
    print(out / 'wire.json')


if __name__ == '__main__':
    main()
