#!/usr/bin/env python3
import unittest
from cluster_stage1_qnx_build_records import collect

class BuildRecordTests(unittest.TestCase):
    def test_two_distinct_records(self):
        data=(b"\x00NAME=first\x00DESCRIPTION=first component\x00DATE=2020\x00\x00"
              b"NAME=second\x00DESCRIPTION=second component\x00\x00")
        rows=collect(data)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["fields"]["DESCRIPTION"],"first component")
        self.assertEqual(rows[1]["fields"]["NAME"],"second")
        self.assertNotIn("second component",str(rows[0]))
    def test_skip_embedded_name(self):
        self.assertEqual(collect(b"xxxNAME=fake\x00"),[])
    def test_boundary_on_nonfield(self):
        rows=collect(b"\x00NAME=one\x00DESCRIPTION=test\x00binary\x00DATE=bad\x00")
        self.assertEqual(len(rows),1)
        self.assertNotIn("DATE",rows[0]["fields"])

if __name__=="__main__":
    unittest.main()
