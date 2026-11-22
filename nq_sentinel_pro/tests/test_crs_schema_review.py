import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sentinel.crs import oneoff

class SchemaReviewTests(unittest.TestCase):
    def test_unit_is_not_inferred_from_numeric_field(self):
        result=oneoff.assess_body(b'{"refRates":[{"type":"SOFR","effectiveDate":"2026-11-19","percent":3}]}','sofr')
        self.assertEqual(result['schema_validation'],'PASS')
        self.assertEqual(result['date_validation'],'PASS')
        self.assertEqual(result['unit_validation'],'UNKNOWN')
        self.assertEqual(result['record_count'],1)
    def test_date_failure_does_not_become_schema_failure(self):
        r=oneoff.assess_body(b'{"refRates":[{"type":"SOFR","effectiveDate":"2026-11-20","percent":3}]}','sofr')
        self.assertEqual(r['schema_validation'],'PASS')
        self.assertEqual(r['date_validation'],'FAIL')
    def test_failure_reasons_are_distinct_and_non_sensitive(self):
        cases=[(b'not json','JSON_INVALID'),(b'{}','CONTAINER_MISSING'),(b'{"refRates":{}}','CONTAINER_TYPE'),(b'{"refRates":[]}','ROW_COUNT')]
        for raw,reason in cases:
            self.assertEqual(oneoff.assess_body(raw,'sofr')['reason'],reason)
    def test_consumed_authority_denied_from_any_directory_before_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(oneoff.http.client,'HTTPSConnection') as transport:
            previous=os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(PermissionError):oneoff.run_once('7077794290',True)
            finally:os.chdir(previous)
            transport.assert_not_called()
