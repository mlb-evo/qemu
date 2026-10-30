"""Q7 0378 long coding -> ConfigM l4c signals, for local research only.

Run: PYTHONPATH=tools/fpk1 python3 -m hmi.configm HEX
Boot: build_fpk1/run.sh --coding HEX

The KSS routine at 0x1086094 reads the 20 raw bytes via 0xc308.
Rte_Write(0xce, element) yields AktuelleParameter; wrappers 0x1038762..
0x103882a map elements 0..6 to l4c 0x127..0x12d. The l4c packer table
is at 0x10cf108. The corresponding GSS callbacks target RTE component
0x34 (table 0x1abdf0). Positions below use byte 0, bit 0 as input bit 0.

Unassigned bits are zeroed, including Units bits 20..23: the original KSS
leaves these stack bits uninitialized. ConfigM_CodedLanguage is assigned
locally in KSS but has no l4c sender/receiver entry in this firmware.
all_signals additionally reproduces InterneCodierung and startup
Fahrzeugerkennung from NvM block 0x39. Its default is the original ROM
fallback, not a recovered device's persisted coding or live CAN identity.
This does not reproduce persisted user overrides.
The saved active design is separate: BAP_DesignChange (0x3cd) is produced
using NvM 0x4b byte 18 and this module does not generate that message.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import os

DEFAULT_CODING = '008500E07C98000801A369602000600000000000'
# Original KSS NvM descriptor 0x10dc44c + 0x39*24 points to 0x10df43c.
DEFAULT_INTERNAL_CODING = '0110086b000009050000171e14017c00'
INTERNAL_LAYOUT = (
    ('Internal_Coding01', 0x12e, tuple(range(8))),
    ('Internal_Coding02', 0x12f, tuple(range(8, 16))),
    ('Application_Coding', 0x130, (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, 27, 28, 30, 31, -1)),
    ('Application_Parameters', 0x267, (40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 54, 55, 56, 63, 64, 65, 66, 67, 68, 69, 70, 30, 31, -1, 72, 73, 74, 75, 76, 77, 78, 79)),
    ('Internal_Variants', 0x273, (80, 81, 82, 83, 84, 96, 97, -1, 86, 87, 100, -1, -1, -1, -1, -1, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 88, 89, 90, 91, 92, 93, 94, 95)),
)

# For each wire bit, the source bit index; -1 means reserved/zero.
LAYOUT = (
    ('Driverassist_Media', 0x127, (13, 31, 38, 35, 34, 47, 45, 44, 43, 42, 118, 40, 41, 79, 87, 86, 85, 116, 0, -1, -1, -1, -1, -1)),
    ('Installation_Coding', 0x128, (15, 14, 12, 11, 10, 28, 37, 36, 33, 32, 84, 83, 82, 81, 97, 96, 102, 101, 100, 29, 76, 80, -1, -1)),
    ('Units', 0x129, (55, 56, 57, 53, 54, 51, 52, 50, 49, 48, 60, 61, 62, 63, 58, 59, 112, 113, 114, 50, -1, -1, -1, -1)),
    ('Vehicle_Specifica', 0x12a, (5, 2, 3, 4, -1, -1, -1, -1, 16, 17, 18, 30, 24, 25, 26, 27, 39, 46, 77, 78, 103, 81, 119, 117)),
    ('View_Specifica', 0x12b, (6, 8, 19, 20, 21, 22, 23, 75, 72, 73, 74, 98, 99, -1, -1, -1, 120, 121, 122, 123, 124, 9, 127, 145)),
    ('BAPStrecke', 0x12c, (95, 94, 93, 92, 91, 90, 89, 88, 111, 110, 109, 108, 107, 106, 131, -1)),
    ('Language', 0x12d, tuple(range(64, 72))),
)


def parse_coding(text):
    try:
        data = bytes.fromhex(text)
    except ValueError as error:
        raise ValueError('Coding must be a hexadecimal string') from error
    if len(data) != 20:
        raise ValueError(f'Coding must contain 20 bytes (40 hex digits), got {len(data)}')
    return data


def signals(coding):
    """Yield (name, l4c dataID, wire value); caller adds the RTE status byte."""
    if len(coding) != 20:
        raise ValueError('Coding must contain exactly 20 bytes')
    raw = int.from_bytes(coding, 'little')
    for name, data_id, bits in LAYOUT:
        value = sum(((raw >> source) & 1) << dest
                    for dest, source in enumerate(bits) if source >= 0)
        yield name, data_id, value.to_bytes(len(bits) // 8, 'little')


def parse_internal(text):
    try:
        data = bytes.fromhex(text)
    except ValueError as error:
        raise ValueError('Internal coding must be hexadecimal') from error
    if len(data) != 16:
        raise ValueError('Internal coding must contain 16 bytes (32 hex digits)')
    return data


def all_signals(coding, internal=None):
    """Fourteen ConfigM messages, using original firmware startup identity rules.

    FPK1_INTERNAL_CODING overrides the ROM fallback for device-specific research.
    Reserved stack bits are zeroed. Layouts were recovered with decode_full in
    configm_oracle.py and checked against the original GSS receiver callbacks.
    """
    if internal is None:
        internal = parse_internal(os.environ.get('FPK1_INTERNAL_CODING', DEFAULT_INTERNAL_CODING))
    if len(internal) != 16:
        raise ValueError('Internal coding must contain exactly 16 bytes')
    for name, key, value in signals(coding):
        if key == 0x128:
            # Installation_Coding bit 22 also depends on internal byte 3 bit 5.
            value = (int.from_bytes(value, 'little') | ((internal[3] >> 5 & 1) << 22)).to_bytes(3, 'little')
        yield name, key, value
    raw = int.from_bytes(internal, 'little')
    for name, key, bits in INTERNAL_LAYOUT:
        value = sum(((raw >> source) & 1) << dest
                    for dest, source in enumerate(bits) if source >= 0)
        yield name, key, value.to_bytes(len(bits) // 8, 'little')
    vehicle = (2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 2, 2, 2, 2, 2)[internal[6] >> 2 & 15]
    primary = (0, 1, 2, 3, 4, 5, 2, 2)[internal[7] >> 1 & 7]
    secondary = (0, 1, 2, 3, 4, 5, 0, 0)[internal[7] >> 4 & 7]
    yield 'Fahrzeugtyp', 0x2d1, bytes([vehicle])
    yield 'Antrieb', 0x2d2, bytes([primary | secondary << 4])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('coding', nargs='?', default=DEFAULT_CODING)
    parser.add_argument('--internal-coding', default=os.environ.get('FPK1_INTERNAL_CODING', DEFAULT_INTERNAL_CODING))
    args = parser.parse_args()
    try:
        coding = parse_coding(args.coding)
        internal = parse_internal(args.internal_coding)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps({'coding': coding.hex().upper(), 'internal_coding': internal.hex(),
        'internal_source': 'ROM fallback' if internal.hex() == DEFAULT_INTERNAL_CODING else 'explicit override', 'signals': [
        {'name': name, 'data_id': hex(data_id), 'wire': value.hex(), 'status': 0}
        for name, data_id, value in all_signals(coding, internal)],
        'identity_source': 'original KSS startup derivation; live CAN recognition absent',
        'user_overrides': False}, indent=2))


if __name__ == '__main__':
    main()
