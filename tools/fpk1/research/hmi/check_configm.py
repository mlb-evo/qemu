"""Check coding masks against original KSS ARM code and test peer delivery.

Use build_fpk1/research-artifacts/configm-venv/bin/python. Requires the
extracted original kss.bin (see configm_oracle.py). All results are local.
"""
import sys
sys.dont_write_bytecode = True
import random
import unittest
from unittest.mock import patch

from configm import (DEFAULT_CODING, DEFAULT_INTERNAL_CODING, parse_coding,
                     INTERNAL_LAYOUT, parse_internal, signals, all_signals)
from configm_oracle import Oracle, REPO
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import gss_ipc_frames as ipc
import kss_peer
from qnx_elf_disasm import Elf
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR


class CodingChecks(unittest.TestCase):
    def test_original_gss_receivers(self):
        elf = Elf(REPO / 'build_fpk1/research-artifacts/hmi-startup/bin/gss_ipc')
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(0x100000, 0x100000)
        cpu.mem_map(0x2000000, 0x10000)
        for kind, offset, address, _, size, *_ in elf.ph:
            if kind == 1:
                cpu.mem_write(address, elf.data[offset:offset + size])
        writes = []
        lengths = (3, 3, 3, 4, 4, 2, 1)

        def receive(cpu, address, size, _):
            if address == 0x162620:
                component = cpu.reg_read(UC_ARM_REG_R0)
                element = cpu.reg_read(UC_ARM_REG_R1)
                pointer = cpu.reg_read(UC_ARM_REG_R2)
                status = cpu.reg_read(UC_ARM_REG_R3)
                writes.append((component, element, status, bytes(cpu.mem_read(pointer, lengths[element]))))
                cpu.emu_stop()

        cpu.hook_add(UC_HOOK_CODE, receive)
        oracle = Oracle()
        coding = parse_coding(DEFAULT_CODING)
        oracle.decode(coding)
        masks = ('ffff07', 'ffff7f', 'ffff0f', '0fffdf00', 'ff1fff00', 'ff7f', 'ff')
        for element, (_, data_id, value) in enumerate(signals(coding)):
            cpu.mem_write(0x2000100, value)
            cpu.mem_write(0x2008000, bytes(0x1000))
            cpu.reg_write(UC_ARM_REG_SP, 0x2009000)
            cpu.reg_write(UC_ARM_REG_LR, 0x2000000)
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_R1, 0x2000100)
            callback = elf.word(0x1abdf0 + data_id * 20 + 16)
            cpu.emu_start(callback, 0x2000000, count=10000)
            self.assertEqual(len(writes), element + 1)
            component, actual_element, status, actual = writes[-1]
            self.assertEqual((component, actual_element, status), (0x34, element, 0))
            mask = bytes.fromhex(masks[element])
            expected = oracle.values[0xce, element]
            self.assertEqual(bytes(a & m for a, m in zip(actual, mask)),
                             bytes(a & m for a, m in zip(expected, mask)))

    def test_original_firmware_bit_masks(self):
        oracle = Oracle()
        rng = random.Random(0x127)
        cases = [bytes(20), bytes([255]) * 20, parse_coding(DEFAULT_CODING)]
        cases += [(1 << bit).to_bytes(20, 'little') for bit in range(160)]
        cases += [rng.randbytes(20) for _ in range(100)]
        for coding in cases:
            reference = oracle.decode(coding)
            # KSS leaks previously used stack bits into Units.reserved.
            reference[0x129] = reference[0x129][:2] + bytes([reference[0x129][2] & 15])
            self.assertEqual({key: value for _, key, value in signals(coding)}, reference, coding.hex())

    def test_peer_delivers_configuration_before_run_and_repeats(self):
        with patch.dict('os.environ', {}, clear=True):
            peer = kss_peer.Kss(lambda text: None, coding=DEFAULT_CODING)
        peer.RUN_REQUEST_DELAY = 0
        peer.handle(7, ipc.CID_GSS_STATUS, b'\x01')
        peer.handle(7, ipc.CID_GSS_STATUS, b'\x01')
        self.assertEqual(len(peer.outbox), 17)
        for frame, (_, key, value) in zip(peer.outbox[2:-1], all_signals(parse_coding(DEFAULT_CODING))):
            self.assertEqual(ipc.parse_frame(frame), [(0x11, 0, ipc.l4c_message(key, value + b'\0'), True)])
        first = peer.next_frame()
        self.assertEqual(peer.next_frame(), first, 'frame retained until ACK')
        while peer.outbox:
            peer.delivered(peer.next_frame())
        peer.tick()
        self.assertEqual(ipc.parse_frame(peer.next_frame())[0][2][:2], b'\x01\x02')
        peer.delivered(peer.next_frame())
        peer.last_alive = 0
        peer.tick()
        self.assertEqual(len(peer.outbox), 18)  # alive, two clamps, fourteen ConfigM, closures

    def test_complete_configuration_against_original_kss(self):
        oracle = Oracle()
        self.assertEqual(oracle.default_internal(), parse_internal(DEFAULT_INTERNAL_CODING))
        rng = random.Random(0x273)
        cases = [(bytes(20), bytes(16)), (bytes([255])*20, bytes([255])*16),
                 (parse_coding(DEFAULT_CODING), oracle.default_internal())]
        cases += [(bytes(20), (1 << bit).to_bytes(16, 'little')) for bit in range(128)]
        cases += [(rng.randbytes(20), rng.randbytes(16)) for _ in range(100)]
        for coding, internal in cases:
            # Firmware leaves reserved bits uninitialized; zero its stack first.
            oracle.cpu.mem_write(0x200e000, bytes(0x1000))
            reference = oracle.decode_full(coding, internal)
            reference[0x129] = reference[0x129][:2] + bytes([reference[0x129][2] & 15])
            for _, key, bits in INTERNAL_LAYOUT:
                mask = sum(1 << dest for dest, source in enumerate(bits) if source >= 0)
                reference[key] = (int.from_bytes(reference[key], 'little') & mask).to_bytes(len(bits)//8, 'little')
            self.assertEqual({key: value for _, key, value in all_signals(coding, internal)},
                             reference, (coding.hex(), internal.hex()))

    def test_complete_wire_roundtrip_through_original_gss(self):
        elf = Elf(REPO / 'build_fpk1/research-artifacts/hmi-startup/bin/gss_ipc')
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(0x100000, 0x100000)
        cpu.mem_map(0x2000000, 0x10000)
        for kind, offset, address, _, size, *_ in elf.ph:
            if kind == 1:
                cpu.mem_write(address, elf.data[offset:offset + size])
        received = []
        sizes = {0x34: (3, 3, 3, 4, 4, 2, 1), 0x35: (1, 1), 0x36: (1, 1, 2, 4, 6)}
        def capture(cpu, address, size, _):
            if address == 0x162620:
                component = cpu.reg_read(UC_ARM_REG_R0)
                element = cpu.reg_read(UC_ARM_REG_R1)
                value = bytes(cpu.mem_read(cpu.reg_read(UC_ARM_REG_R2), sizes[component][element]))
                received.append((component, element, cpu.reg_read(UC_ARM_REG_R3), value))
                cpu.emu_stop()
        cpu.hook_add(UC_HOOK_CODE, capture)
        oracle = Oracle()
        for internal in (bytes(16), bytes([255])*16, oracle.default_internal()):
            for _, key, value in all_signals(parse_coding(DEFAULT_CODING), internal):
                cpu.mem_write(0x2000100, value)
                cpu.mem_write(0x2008000, bytes(0x1000))
                cpu.reg_write(UC_ARM_REG_SP, 0x2009000)
                cpu.reg_write(UC_ARM_REG_LR, 0x2000000)
                cpu.reg_write(UC_ARM_REG_R0, 0)
                cpu.reg_write(UC_ARM_REG_R1, 0x2000100)
                before = len(received)
                cpu.emu_start(elf.word(0x1abdf0 + key*20 + 16), 0x2000000, count=10000)
                self.assertEqual(len(received), before + 1)
                component, element, status, decoded = received[-1]
                self.assertEqual(status, 0)
                expected_component = 0x34 if key <= 0x12d else (0x35 if key >= 0x2d1 else 0x36)
                self.assertEqual(component, expected_component)
                self.assertEqual(oracle.pack(key, decoded), value, hex(key))

    def test_invalid_coding(self):
        for text in ('gg' * 20, '00' * 19, '00' * 21):
            with self.assertRaises(ValueError):
                parse_coding(text)


if __name__ == '__main__':
    unittest.main()
