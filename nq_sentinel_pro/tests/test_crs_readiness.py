import json
import unittest
from sentinel.crs.oneoff import assess_body
from sentinel.crs.authorization import safe_diagnostic

class ReadinessTests(unittest.TestCase):
    def test_all_future_diagnostic_reasons_without_numbers(self):
        row={'type':'SOFR','effectiveDate':'2026-11-19','percent':3}
        cases=[(b'bad','JSON_INVALID'),(b'{}','CONTAINER_MISSING'),(b'{"refRates":{}}','CONTAINER_TYPE'),(b'{"refRates":[]}','ROW_COUNT')]
        for change,expected in (({'percent':True},'RATE_FIELD_TYPE'),({'percent':None},'RATE_FIELD_TYPE'),({'effectiveDate':None},'DATE_FIELD_TYPE'),({'effectiveDate':'bad'},'DATE_FORMAT')):
            cases.append((json.dumps({'refRates':[{**row,**change}]}).encode(),expected))
        for payload,expected in cases:
            result=assess_body(payload,'sofr')
            self.assertEqual(result['reason'],expected)
            self.assertNotIn('percent',result)
            self.assertEqual(result['unit_validation'],'UNKNOWN')

    def test_wrong_envelope_is_not_guessed(self):
        result=assess_body(b'{"data":{"refRates":[]}}','sofr')
        self.assertEqual(result['reason'],'CONTAINER_MISSING')

    def test_unapproved_diagnostic_expansion_is_rejected(self):
        for extra in ('reason','date_validation','body_sha256','url','query_key','exception_message'):
            with self.assertRaises(ValueError):safe_diagnostic({extra:'unapproved'})
