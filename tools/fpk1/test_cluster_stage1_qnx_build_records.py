#!/usr/bin/env python3
import unittest
from cluster_stage1_qnx_build_records import collect

class BuildRecordTests(unittest.TestCase):
    def test_two_records_without_nulls(self):
        data=b"NAME=first\nDESCRIPTION=first component\nNAME=second\nDESCRIPTION=second component\n"
        rows=collect(data)
        self.assertEqual(len(rows),2)
        self.assertIn("first component",rows[0]["fields"]["DESCRIPTION"])
        self.assertEqual(rows[1]["fields"]["NAME"],"second")
    def test_non_null_prefix(self):
        rows=collect(b"QNX_BUILD_NAME=driver\nDESCRIPTION=driver component\n")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["fields"]["NAME"],"driver")
    def test_metadata_without_name(self):
        self.assertEqual(collect(b"DESCRIPTION=orphan\nDATE=2020\n"),[])
    def test_null_separator(self):
        rows=collect(b"\x00NAME=one\x00DESCRIPTION=test\x00NAME=two\x00")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["fields"]["DESCRIPTION"],"test")
if __name__=="__main__":
    unittest.main()
