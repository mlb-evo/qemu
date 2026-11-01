"""Local GTF2 experiment: turn the Map display "Traffic" item into "CarPlay".

Writes a patched copy of the private Q7 0378 gtf2 to
build_fpk1/research-artifacts/navigation/<run>/gtf2 (plus patch.json); the
original executable is only read. Every edit checks the original bytes and
disassembles the result, so a different firmware build fails loudly.

What changes (addresses are virtual, file offset = VA - 0x100000):
- sendMapDisplay table 0x7d1af4 [1, 0, 2] -> [1, 0, 3]: item index 3 (the
  third, formerly "Verkehr"/Traffic, widget) sends MapView 3.
- setMapDisplayAvailable 0x17659c: the item's visibility DP 0x4000071 follows
  SupportedMapViews bit 3 instead of bit 2.
- Status receive 0x178d68: MapView 0..3 maps through a new table
  [2, 1, 0, 3] (Standard, Google Earth, none, CarPlay) to the active index.
- sendStageInfo 0x176e14: the "before setting bits" trace is replaced by
  ASG_HMI_State bit 1 = (requested MapView +0x98d == 3); the Status handler
  only compares bit 0 with the stage, so the extra bit cannot loop.
- sendMapDisplay 0x177388 calls a trampoline that sends the MapView SetGet
  (startNextMORequest) and then sendStageInfo, under the caller's lock.
- The third map-display label in every language set becomes "CarPlay"
  ("CPlay" where the slot is shorter than seven bytes).
The new table and trampoline live in the unreferenced DP-name string
"Nav_Submenu_MapDisplay_StandardMap_visible" inside the R+X text segment.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import datetime
import hashlib
import json
import re
import struct
from pathlib import Path
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'build_fpk1/research-artifacts/python-libs'))
import capstone

SHA256 = '6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1'
BASE = 0x100000
TEXT_END = 0x9634dc
CAVE_NAME = b'Nav_Submenu_MapDisplay_StandardMap_visible'
CAVE = 0x804164                  # 4-aligned inside the cave string
TABLE, TRAMPOLINE = CAVE, CAVE + 16
START_NEXT_MO, SEND_STAGE_INFO = 0x177150, 0x176de0


def branch(at, target, link):
    return (0xeb000000 if link else 0xea000000) | ((target - at - 8) >> 2) & 0xffffff


def words(*values):
    return struct.pack(f'<{len(values)}I', *values)


# (VA, original bytes, new bytes, expected disassembly of new code or None for data)
EDITS = [
    ('sendMapDisplay index 3 -> MapView 3', 0x7d1afc, words(2), words(3), None),
    ('Traffic item visibility from SupportedMapViews bit 3', 0x17659c,
     words(0xe7e01154), words(0xe7e011d4), ['ubfx r1, r4, #3, #1']),
    ('receive bound MapView <= 3', 0x178d68, words(0xe3530002), words(0xe3530003), ['cmp r3, #3']),
    ('receive table pointer', 0x178dd8, words(0x7d1b08), words(TABLE), None),
    ('ASG_HMI_State bit 1 = MapView 3 requested', 0x176e14,
     words(0xe59f0088, 0xe5d458b0, 0xe1d033f8, 0xe3530001, 0xca000003,
           0xe3a01001, 0xe59f2078, 0xe1a03005, 0xebfe5d0a),
     words(0xe5d458b0, 0xe5d4398d, 0xe3530003, 0x03855002, 0x13c55002,
           0xe320f000, 0xe320f000, 0xe320f000, 0xe320f000),
     ['ldrb r5, [r4, #0x8b0]', 'ldrb r3, [r4, #0x98d]', 'cmp r3, #3', 'orreq r5, r5, #2',
      'bicne r5, r5, #2', 'nop', 'nop', 'nop', 'nop']),
    ('sendMapDisplay -> trampoline', 0x177388, words(branch(0x177388, START_NEXT_MO, True)),
     words(branch(0x177388, TRAMPOLINE, True)), [f'bl #{TRAMPOLINE:#x}']),
]


def cave_edits(data):
    offset = data.index(b'\0' + CAVE_NAME + b'\0') + 1
    start, end = offset + BASE, offset + BASE + len(CAVE_NAME)
    code = words(0xe92d4010, 0xe1a04000, branch(TRAMPOLINE + 8, START_NEXT_MO, True),
                 0xe1a00004, 0xe8bd4010, branch(TRAMPOLINE + 20, SEND_STAGE_INFO, False))
    table = words(2, 1, 0, 3)
    if not (start <= TABLE and TRAMPOLINE + len(code) <= end):
        raise SystemExit('cave does not fit the DP-name string')
    original = data[TABLE - BASE:TRAMPOLINE + len(code) - BASE]
    return [('receive table [2, 1, 0, 3] (cave)', TABLE, original[:16], table, None),
            ('trampoline: startNextMORequest + sendStageInfo (cave)', TRAMPOLINE, original[16:], code,
             ['push {r4, lr}', 'mov r4, r0', f'bl #{START_NEXT_MO:#x}', 'mov r0, r4',
              'pop {r4, lr}', f'b #{SEND_STAGE_INFO:#x}'])]


def label_edits(data):
    """The string after "Google Earth" in each language set: standard | GE | traffic | orient, orient."""
    edits = []
    for m in re.finditer(rb'\0([^\0]+)\0([^\0]*Google Earth[^\0]*)\0([^\0]+)\0([^\0]+)\0\4\0', data[:TEXT_END]):
        old = m[3]
        new = (b'CarPlay' if len(old) >= 7 else b'CPlay').ljust(len(old), b'\0')
        edits.append((f'label {old.decode()!r}', m.start(3) + BASE, old, new, None))
    return edits


def check_unreferenced(data, start, end):
    count = len(data[:TEXT_END]) // 4
    for value in struct.unpack_from(f'<{count}I', data):
        if start <= value < end:
            raise SystemExit(f'cave string is referenced ({value:#x})')


def apply(data):
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    offset = data.index(b'\0' + CAVE_NAME + b'\0') + 1
    check_unreferenced(data, offset + BASE, offset + BASE + len(CAVE_NAME) + 1)
    out = bytearray(data)
    report = []
    for name, va, old, new, expected in EDITS + cave_edits(data) + label_edits(data):
        at = va - BASE
        if not 0 <= at < TEXT_END or bytes(out[at:at + len(old)]) != old or len(old) != len(new):
            raise SystemExit(f'unexpected original bytes for {name} at {va:#x}')
        out[at:at + len(new)] = new
        if expected is not None:
            text = [f'{i.mnemonic} {i.op_str}'.strip() for i in md.disasm(new, va)]
            if text != expected:
                raise SystemExit(f'{name}: {text} != {expected}')
        report.append(dict(name=name, va=f'{va:#x}', old=old.hex(), new=new.hex()))
    return bytes(out), report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, default=REPO / 'build_fpk1/research-artifacts/wheel/gtf2')
    parser.add_argument('--out', type=Path, help='output directory (default: navigation/<timestamp>-carplay)')
    args = parser.parse_args()
    data = args.input.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('unexpected gtf2 build')
    patched, report = apply(data)
    out = args.out or (REPO / 'build_fpk1/research-artifacts/navigation'
                       / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-carplay'))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'gtf2').write_bytes(patched)
    (out / 'patch.json').write_text(json.dumps(dict(
        input=str(args.input), input_sha256=SHA256, output_sha256=hashlib.sha256(patched).hexdigest(),
        edits=report), indent=2) + '\n')
    for item in report:
        print(item['va'], item['name'])
    print(out / 'gtf2')


if __name__ == '__main__':
    main()
