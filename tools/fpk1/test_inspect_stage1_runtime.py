import struct
import unittest

from inspect_stage1_runtime import execution_samples, storage_evidence


def fixture(address=0x102954, code=bytes(range(32)), path='bin/sifsloader'):
    elf = bytearray(84)
    elf[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<I', elf, 28, 52)
    struct.pack_into('<HH', elf, 42, 32, 1)
    struct.pack_into('<8I', elf, 52, 1, 84, address, 0, len(code), len(code), 5, 4)
    elf += code
    return bytes(elf), {'entries': [dict(kind='regular', path=path, offset=0, size=len(elf))]}


def translated(address=0x102954, code=bytes(range(32))):
    return f'0x{address:08x}:  \nOBJD-T: {code.hex()}\n\n'


def executed(address=0x102954, native='0x12340000', result=0, decoded=0):
    registers = {0: result, 2: decoded, 15: address}
    rows = [' '.join(f'R{i:02d}={registers.get(i, 0):08x}' for i in range(start, start + 4))
            for start in range(0, 16, 4)]
    return (f'Trace 3: {native} [00000000/{address:016x}/00000000/00000000] \n' +
            '\n'.join(rows) + '\nPSR=6000001f -ZC- A sys32\n')


class StorageRuntimeTests(unittest.TestCase):
    def test_native_tb_identity_separates_equal_guest_addresses(self):
        image, catalog = fixture()
        text = translated() + executed() + translated(code=bytes([255]) * 32)
        text += executed(native='0x22340000', result=99) + executed(result=7)
        result = storage_evidence(text, image, catalog)['checkpoints']['mount_return']
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['r0_counts'], {'0x0': 1, '0x7': 1})

    def test_tb_identity_can_be_retranslated(self):
        text = translated() + executed() + translated(code=bytes([255]) * 32) + executed()
        rows = list(execution_samples(text))
        self.assertEqual(rows[0]['code'], bytes(range(32)))
        self.assertEqual(rows[1]['code'], bytes([255]) * 32)

    def test_unknown_or_different_pc_has_no_byte_evidence(self):
        self.assertEqual(list(execution_samples(executed())), [])
        self.assertEqual(list(execution_samples(translated() + executed(address=0x102958))), [])
        self.assertEqual(list(execution_samples(translated())), [])

    def test_ambiguous_or_wrong_file_is_rejected(self):
        image, catalog = fixture()
        text = translated() + executed()
        catalog['entries'].append(dict(kind='regular', path='bin/other', offset=0, size=len(image)))
        self.assertEqual(storage_evidence(text, image, catalog)['checkpoints'], {})
        image, catalog = fixture(path='bin/other')
        self.assertEqual(storage_evidence(text, image, catalog)['checkpoints'], {})

    def test_emmc_checkpoint_requires_its_catalog_file(self):
        address = 0x107638
        image, catalog = fixture(address, path='bin/driver/devb-mmcsd-tegra3-devlite')
        row = storage_evidence(translated(address) + executed(address), image, catalog)
        self.assertEqual(row['checkpoints']['emmc_io_privilege_return']['r0_counts'], {'0x0': 1})
        catalog['entries'][0]['path'] = 'bin/sifsloader'
        self.assertEqual(storage_evidence(translated(address) + executed(address), image, catalog)['checkpoints'], {})

    def test_controller_trace_is_separate_from_program_identity(self):
        image, catalog = fixture()
        text = 'sdhci_send_command CMD01 ARG[0x40ff8080]\nsdhci_error command timed out\n'
        result = storage_evidence(text, image, catalog)
        self.assertEqual(result['checkpoints'], {})
        self.assertEqual(result['sdmmc_command_count'], 1)
        self.assertEqual(result['sdmmc_commands'], [dict(command=1, argument='0x40ff8080')])
        self.assertEqual(result['sdmmc_errors'], ['command timed out'])

    def test_short_and_truncated_byte_evidence_is_rejected(self):
        image, catalog = fixture()
        for text in (translated(code=bytes(4)) + executed(), translated() + executed()):
            candidate = image if 'OBJD-T: 00000000\n' in text else image[:-1]
            self.assertEqual(storage_evidence(text, candidate, catalog)['checkpoints'], {})
        self.assertEqual(list(execution_samples('0x00102954: \nOBJD-T: abc\n' + executed())), [])

    def test_all_lzo_results_aggregate_beyond_sample_limit(self):
        address = 0x10312c
        image, catalog = fixture(address)
        text = translated(address)
        text += ''.join(executed(address, result=0, decoded=n) for n in (10, 20, 30, 40))
        row = storage_evidence(text, image, catalog)['checkpoints']['lzo_return']
        self.assertEqual(row['count'], 4)
        self.assertEqual(len(row['samples']), 3)
        self.assertEqual(row['decoded_bytes_total'], 100)
        self.assertEqual(row['r0_counts'], {'0x0': 4})

    def test_diagnostic_string_only_from_catalog_file(self):
        address = 0x104124
        code = bytes(range(32)) + b'test message\0'
        image, catalog = fixture(address, code)
        text = translated(address, code[:32]) + executed(address)
        # r1 is a format pointer. Other registers and heap pointers stay opaque.
        text = text.replace('R01=00000000', f'R01={address + 32:08x}')
        row = storage_evidence(text, image, catalog)['checkpoints']['diagnostic']
        self.assertEqual(row['samples'][0]['format'], 'test message')
        text = text.replace(f'R01={address + 32:08x}', 'R01=ffffffff')
        row = storage_evidence(text, image, catalog)['checkpoints']['diagnostic']
        self.assertNotIn('format', row['samples'][0])

    def test_non_executable_segment_and_bad_phdr_are_rejected(self):
        image, catalog = fixture()
        text = translated() + executed()
        bad = bytearray(image)
        struct.pack_into('<I', bad, 52 + 24, 4)
        self.assertEqual(storage_evidence(text, bad, catalog)['checkpoints'], {})
        struct.pack_into('<I', bad, 28, 0xfffffff0)
        self.assertEqual(storage_evidence(text, bad, catalog)['checkpoints'], {})


if __name__ == '__main__':
    unittest.main()
