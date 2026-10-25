import struct
import unittest
from unittest.mock import patch
from probe_stage1_startup import build_atags, fault_context, parse_registers, probe, match_entry_traces


class StartupProbeTests(unittest.TestCase):
    def test_atag_lengths_memory_and_delimiter(self):
        command = 'mem=512M@0x80000000 '
        data = build_atags(command)
        cursor, tags = 0, []
        while True:
            words, kind = struct.unpack_from('<II', data, cursor)
            if words == 0:
                self.assertEqual(kind, 0)
                self.assertEqual(cursor + 8, len(data))
                break
            tags.append((kind, data[cursor + 8:cursor + words * 4]))
            cursor += words * 4
        self.assertEqual([kind for kind, _ in tags], [0x54410001, 0x54410002, 0x54410009])
        self.assertEqual(struct.unpack('<II', tags[1][1]), (512 << 20, 0x80000000))
        self.assertEqual(tags[2][1].split(b'\0')[0].decode(), command)

    def test_exact_cmdline_is_not_silently_changed(self):
        data = build_atags('mem=512M@0x80000000')
        self.assertIn(b'mem=512M@0x80000000\0', data)
        self.assertNotIn(b'mem=512M@0x80000000 \0', data)

    def test_bad_atag_inputs(self):
        for command in ('', 'a\0b', 'a\nb', 'x' * 1024):
            with self.subTest(command=repr(command)[:30]), self.assertRaises(ValueError):
                build_atags(command)
        for size in (0, 2049):
            with self.subTest(size=size), self.assertRaises(ValueError):
                build_atags('mem=1M ', size)

    def test_fault_registers_come_before_exception(self):
        state = ('R00=00000000 R01=00000000 R02=00000000 R03=ffffffff\n'
                 'R04=00000000 R05=00000000 R06=00000000 R07=00000000\n'
                 'R08=00000000 R09=00000000 R10=00000000 R11=00000000\n'
                 'R12=00000000 R13=80a19b50 R14=80a08064 R15=80a013b8\n'
                 'PSR=a00001d3 N-C- A svc32\n')
        exception = ('Taking exception 4 [Data Abort] on CPU 5\n'
                     '...from EL1 to EL1\n...with ESR 0x25/0x9600003f\n'
                     '...with DFSR 0x1 DFAR 0x3\n')
        row = fault_context(state + exception + state.replace('80a013b8', '00000010'))
        self.assertEqual(row['registers']['r15'], '0x80a013b8')
        self.assertEqual(row['registers']['r3'], '0xffffffff')
        self.assertTrue(row['precise_instruction_trace'])
        self.assertIn('DFAR 0x3', row['exception'][3])

    def test_invalid_experiment_bounds_before_loading_firmware(self):
        for options in ({'run_ms': 10001}, {'trace_limit_kib': 15}, {'trace_limit_kib': 8193},
                        {'icount_shift': 0}, {'icount_shift': 0, 'tcg_thread': 'multi'},
                        {'icount_shift': -1, 'tcg_thread': 'single'},
                        {'icount_shift': 11, 'tcg_thread': 'single'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                probe('missing-firmware', 'missing-qemu', **options)

    def test_kernel_state_rejects_other_firmware_profile(self):
        with patch('probe_stage1_startup.decode_archive', return_value=(b'', {'decoded_sha256': 'other'})):
            with self.assertRaisesRegex(ValueError, 'only apply to the verified'):
                probe('other-firmware', 'missing-qemu', kernel_state=True)

    def test_svc_is_not_a_fault(self):
        self.assertIsNone(fault_context('Taking exception 2 [SVC] on CPU 0\n'))
        row = fault_context('Taking exception 4 [Data Abort] on CPU 5\n')
        self.assertEqual(row['registers'], {})
        self.assertFalse(row['precise_instruction_trace'])
        self.assertEqual(parse_registers('CPU#0\nR15=fe0762f4\n')[15], 0xfe0762f4)


class EntryTraceTests(unittest.TestCase):
    def fixture(self, code=bytes(range(32)), entry=0x100000):
        elf = bytearray(84)
        elf[:6] = b'\x7fELF\x01\x01'
        struct.pack_into('<II', elf, 24, entry, 52)
        struct.pack_into('<HH', elf, 42, 32, 1)
        struct.pack_into('<8I', elf, 52, 1, 84, entry, 0, len(code), len(code), 5, 4)
        elf += code
        catalog = {'entries': [dict(path='bin/example', offset=0, size=len(elf))]}
        trace = f'0x{entry:08x}:  \nOBJD-T: {code[:16].hex()}\nOBJD-T: {code[16:].hex()}\n'
        trace += f'Trace 0: 0x12340000 [00000000/{entry:016x}/00000000/00000000] \n'
        return trace, bytes(elf), catalog

    def test_entry_requires_matching_bytes(self):
        trace, image, catalog = self.fixture()
        rows = match_entry_traces(trace, image, catalog)
        self.assertEqual(rows, [dict(path='bin/example', entry='0x100000', matched_bytes=32,
                                    unique_at_entry_within_catalog=True)])
        self.assertEqual(match_entry_traces(trace.replace('00010203', 'ffffffff'), image, catalog), [])

    def test_shared_entry_stubs_remain_ambiguous(self):
        trace, image, catalog = self.fixture()
        catalog['entries'].append(dict(path='bin/alias', offset=0, size=len(image)))
        rows = match_entry_traces(trace, image, catalog)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(not row['unique_at_entry_within_catalog'] for row in rows))

    def test_address_or_assembly_alone_is_insufficient(self):
        trace, image, catalog = self.fixture()
        self.assertEqual(match_entry_traces(trace.replace('00100000', '00100004'), image, catalog), [])
        self.assertEqual(match_entry_traces('0x00100000: mov r0,r0\n', image, catalog), [])
        self.assertEqual(match_entry_traces(trace.split('Trace 0:')[0], image, catalog), [])

    def test_short_or_out_of_file_evidence_is_rejected(self):
        trace, image, catalog = self.fixture(code=bytes(8))
        self.assertEqual(match_entry_traces(trace, image, catalog), [])
        trace, image, catalog = self.fixture()
        self.assertEqual(match_entry_traces(trace, image[:-1], catalog), [])


if __name__ == '__main__':
    unittest.main()
