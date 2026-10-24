#!/usr/bin/env python3
"""Firmware-free regression tests for independent Stage1 LZF decoders.

Uses synthetic LZF wire bytes, including overlapping distance-1 references,
long matches, offsets, truncation and output caps. No firmware required.
"""
import unittest
from probe_stage1_lzf import decode as strict_decode
from validate_stage1_unseeded_lzf import decode as suffix_decode

def decode_pair(encoded):
    strict=strict_decode(encoded)
    suffix,end,err=suffix_decode(encoded,0)
    assert err is None,(end,err)
    assert end==len(encoded)
    return strict,bytes(suffix)

class LZFTests(unittest.TestCase):
    def check(self,encoded,expected):
        for decoded in decode_pair(encoded):
            self.assertEqual(decoded,expected)
    def test_literal(self):
        self.check(b"\x06\x7fELF\x01\x01\x01",b"\x7fELF\x01\x01\x01")
    def test_distance_one_short(self):
        # one literal 'A', then 3 copies of A (ctrl 0x20 => len 3)
        self.check(b"\x00A\x20\x00",b"A"*4)
    def test_long_run(self):
        # ctrl E0 + extension FF: (7+255+2)=264 bytes copied
        self.check(b"\x00Z\xe0\xff\x00",b"Z"*265)
    def test_consecutive_long_runs(self):
        self.check(b"\x00Z"+b"\xe0\xff\x00"*3,b"Z"*(1+264*3))
    def test_nonoverlap_reference(self):
        # 'ABCD' then copy previous four at distance four
        self.check(b"\x03ABCD\x40\x03",b"ABCDABCD")
    def test_nonoverlap_shorter_than_distance(self):
        # Five literal bytes, then copy three from five bytes back.
        self.check(b"\x04ABCDE\x20\x04",b"ABCDEABC")
    def test_equal_distance_and_length_three(self):
        self.check(b"\x02ABC\x20\x02",b"ABCABC")

    def test_overlap_reference(self):
        # 'AB', then copy six at distance two
        self.check(b"\x01AB\x80\x01",b"ABABABAB")
    def test_mixed_elf_after_repeats(self):
        raw=b"\x00Z"+b"\xe0\xff\x00"*2+b"\x06\x7fELF\x01\x01\x01"
        self.check(raw,b"Z"*(1+264*2)+b"\x7fELF\x01\x01\x01")
    def test_invalid_reference(self):
        with self.assertRaises(ValueError):strict_decode(b"\x20\x00")
        _,_,error=suffix_decode(b"\x20\x00",0)
        self.assertEqual(error,"invalid backreference")
    def test_truncated_literal(self):
        with self.assertRaises(ValueError):strict_decode(b"\x03AB")
        _,_,error=suffix_decode(b"\x03AB",0)
        self.assertEqual(error,"truncated literal")
    def test_cap(self):
        with self.assertRaises(ValueError):strict_decode(b"\x00Z\xe0\xff\x00",limit=100)
        _,_,error=suffix_decode(b"\x00Z\xe0\xff\x00",0,limit=100)
        self.assertEqual(error,"output limit")
if __name__=="__main__":unittest.main()
