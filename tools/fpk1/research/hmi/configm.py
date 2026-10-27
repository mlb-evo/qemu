"""Q7 0378 long coding -> ConfigM l4c signals, for local research only.

Run: python3 tools/fpk1/research/hmi/configm.py HEX
Boot: build_fpk1/run.sh --coding HEX

The KSS routine at 0x1086094 reads the 20 raw bytes via 0xc308.
Rte_Write(0xce, element) yields AktuelleParameter; wrappers 0x1038762..
0x103882a map elements 0..6 to l4c 0x127..0x12d. The l4c packer table
is at 0x10cf108. The corresponding GSS callbacks target RTE component
0x34 (table 0x1abdf0). Positions below use byte 0, bit 0 as input bit 0.

Unassigned bits are zeroed, including Units bits 20..23: the original KSS
leaves these stack bits uninitialized. ConfigM_CodedLanguage is assigned
locally in KSS but has no l4c sender/receiver entry in this firmware.
InterneCodierung and Fahrzeugerkennung require separate KSS data and are
deliberately absent. This does not reproduce persisted user overrides.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json

DEFAULT_CODING = '008500E07C98000801A369602000600000000000'

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('coding', nargs='?', default=DEFAULT_CODING)
    args = parser.parse_args()
    try:
        coding = parse_coding(args.coding)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps({'coding': coding.hex().upper(), 'signals': [
        {'name': name, 'data_id': hex(data_id), 'wire': value.hex(), 'status': 0}
        for name, data_id, value in signals(coding)],
        'missing_sources': ['InterneCodierung', 'Fahrzeugerkennung'],
        'user_overrides': False}, indent=2))


if __name__ == '__main__':
    main()
