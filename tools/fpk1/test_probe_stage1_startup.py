import struct
import unittest
from probe_stage1_startup import build_atags, fault_context, parse_registers


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

    def test_svc_is_not_a_fault(self):
        self.assertIsNone(fault_context('Taking exception 2 [SVC] on CPU 0\n'))
        row = fault_context('Taking exception 4 [Data Abort] on CPU 5\n')
        self.assertEqual(row['registers'], {})
        self.assertFalse(row['precise_instruction_trace'])
        self.assertEqual(parse_registers('CPU#0\nR15=fe0762f4\n')[15], 0xfe0762f4)


if __name__ == '__main__':
    unittest.main()
