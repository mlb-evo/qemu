"""Local static report on the GTF2 Map display submenu; outputs stay private.

Writes build_fpk1/research-artifacts/navigation/mapdisplay-static.txt with:
- DP IDs of the Nav_SideMenusNav_* / Nav_Submenu_* names, reconstructed from
  their ASCII order (the generator numbered them from 0x400005f) and checked
  against the DP literals of the known writers;
- the outline of CHMISvNavSubmenuMapdisplayViewData::construct per item
  (node path strings, ViewData member stores, DP and property literals);
- the radio "checked" guards that read Nav_Submenu_ActiveMapDisplay;
- the press handlers, send/receive tables and the per-language item texts;
- the absolute-reference check for the DP-name strings (used as a code cave).
"""
import sys
sys.dont_write_bytecode = True
import re
import struct
from pathlib import Path
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
sys.path.insert(0, str(REPO / 'build_fpk1/research-artifacts/python-libs'))
from qnx_elf_disasm import Elf, instructions, annotate

GTF2 = REPO / 'build_fpk1/research-artifacts/wheel/gtf2'
CONSTRUCT = (0x4702e0, 0x4737cc)
PROCESS_DP = (0x46364c, 0x464320)
GUARDS = (0x60f000, 0x612000)
# Writers whose DP literal fixes the meaning of an ID (function, DP, name).
KNOWN = [(0x1764f4, 0x4000061, 'Nav_SideMenusNav_MapDisplay_visible'),
         (0x1764f4, 0x4000070, 'Nav_Submenu_MapDisplay_StandardMap_visible (bit 0)'),
         (0x1764f4, 0x400006f, 'Nav_Submenu_MapDisplay_GoogleMap_visible (bit 1)'),
         (0x1764f4, 0x4000071, 'Nav_Submenu_MapDisplay_TrafficMap_visible (bit 2)'),
         (0x1772f4, 0x4000066, 'Nav_Submenu_ActiveMapDisplay (sendMapDisplay)')]


def dp_names(elf):
    names = set(re.findall(rb'(?<=\0)(Nav_(?:SideMenusNav|Submenu)_[A-Za-z0-9_]+)(?=\0)', elf.data))
    return {0x400005f + n: name.decode() for n, name in enumerate(sorted(names))}


def literal(elf, ins):
    m = re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]', ins.op_str)
    return elf.word(ins.address + 8 + int(m[1], 0)) if m and ins.mnemonic.startswith('ldr') else None


def main():
    elf = Elf(GTF2)
    out = []
    put = out.append
    names = dp_names(elf)
    put('# DP IDs by ASCII order of Nav_SideMenusNav_*/Nav_Submenu_* names (base 0x400005f)')
    for dp, name in names.items():
        put(f'{dp:#x} {name}')
    put('\n# cross-check with writer literals')
    for function, dp, meaning in KNOWN:
        seen = any(literal(elf, i) == dp for i in instructions(elf, function, function + 0xd0))
        put(f'{dp:#x} {"ok " if seen and names.get(dp, "") in meaning else "BAD"} {meaning}')

    put('\n# construct outline (strings, DP/property literals, member stores)')
    for ins in instructions(elf, *CONSTRUCT):
        value = literal(elf, ins)
        text = annotate(elf, ins)
        if (value is not None and (elf.cstr(value) or value >> 24 in (2, 4, 6))) \
                or re.match(r'str\w* \w+, \[r4, (#0x[0-9a-f]{3,}|r\d)\]', f'{ins.mnemonic} {ins.op_str}'):
            put(text)

    put('\n# processDPEvent DP comparisons')
    for ins in instructions(elf, *PROCESS_DP):
        value = literal(elf, ins)
        if value is not None and value >> 24 == 4:
            put(f'{ins.address:#x}: {value:#x} {names.get(value, "")}')

    put('\n# guards reading a DP and comparing with a constant (radio checked)')
    window = []
    for ins in instructions(elf, *GUARDS):
        window = (window + [ins])[-6:]
        if ins.mnemonic == 'cmp' and ins.op_str.startswith('r0, #'):
            dps = [literal(elf, i) for i in window if literal(elf, i)]
            if dps and dps[0] >> 24 == 4:
                put(f'{window[0].address:#x}: {names.get(dps[0], hex(dps[0]))} == {ins.op_str[5:]}')

    put('\n# press handlers -> sendMapDisplay(index)')
    for ins in instructions(elf, 0x17c37c, 0x17c3f4):
        if ins.mnemonic in ('mov', 'bl') and (ins.op_str.startswith('r1, #') or ins.mnemonic == 'bl') \
                or (literal(elf, ins) and elf.cstr(literal(elf, ins))):
            put(annotate(elf, ins))
    put('send table 0x7d1af4 (index-1 -> MapView): '
        + str(struct.unpack('<3I', elf.data[elf.off(0x7d1af4):elf.off(0x7d1af4) + 12])))
    put('recv table 0x7d1b08 (MapView -> index): '
        + str(struct.unpack('<3I', elf.data[elf.off(0x7d1b08):elf.off(0x7d1b08) + 12])))

    put('\n# per-language item texts (Standard | Google Earth | Traffic)')
    for m in re.finditer(rb'\0([^\0]+)\0([^\0]*Google Earth[^\0]*)\0([^\0]+)\0([^\0]+)\0\4\0', elf.data):
        put(f'{m.start(3) + 0x100000:#x}: ' + ' | '.join(m[i].decode('utf-8', 'replace') for i in (1, 2, 3)))

    put('\n# absolute references to the DP-name strings (expected none)')
    count = len(elf.data) // 4
    words = set(struct.unpack_from(f'<{count}I', elf.data))
    for dp in (0x400006f, 0x4000070, 0x4000071, 0x4000061, 0x4000066):
        offset = elf.data.index(b'\0' + names[dp].encode() + b'\0') + 1
        refs = [va for va in range(offset + 0x100000, offset + 0x100000 + len(names[dp])) if va in words]
        put(f'{names[dp]} at {offset + 0x100000:#x}: {[hex(r) for r in refs]}')

    path = REPO / 'build_fpk1/research-artifacts/navigation/mapdisplay-static.txt'
    path.write_text('\n'.join(out) + '\n')
    print(path)


if __name__ == '__main__':
    main()
