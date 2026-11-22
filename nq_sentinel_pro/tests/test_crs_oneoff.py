import unittest
from sentinel.crs.oneoff import check_body

class OneOffTests(unittest.TestCase):
    def test_valid_synthetic_contract(self):
        self.assertEqual(check_body(b'{"refRates":[{"type":"SOFR","effectiveDate":"2026-11-19","percent":3}]}','sofr'), 'NONE')
    def test_no_alias_or_future_or_duplicate(self):
        for body in (b'{}', b'{"refRates":[]}', b'{"refRates":[{"type":"SOFR","effectiveDate":"2026-11-19","percentRate":3}]}'):
            self.assertNotEqual(check_body(body,'sofr'), 'NONE')
    def test_errors_never_return_body(self):
        self.assertEqual(check_body(b'SECRET_RESPONSE','sofr'), 'SCHEMA_MISMATCH')
