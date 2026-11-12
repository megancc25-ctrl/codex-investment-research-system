import io
import json
import tempfile
import unittest
from pathlib import Path
from sentinel.point_in_time import validate_record, audit
from sentinel.free_sources import (sec_gaap_facts, cboe_vix, finra_margin,
                                    constituents, tsmc_revenue, valuation_earnings)

class MockResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n=-1): return self.payload

class FreeAdaptersTests(unittest.TestCase):
    def test_lookahead_and_retrieval(self):
        base = dict(indicator="HY_OAS", value=4.1, unit="pct_points",
                    observation_date="2026-11-10",
                    published_at="2026-11-11T14:00:00Z",
                    retrieved_at="2026-11-11T15:00:00Z",
                    source_url="https://fred.stlouisfed.org/", source_kind="FRED")
        self.assertTrue(validate_record(base,"2026-11-11T16:00:00Z")["usable"])
        self.assertEqual(validate_record(base,"2026-11-11T13:00:00Z")["reason"],"LOOKAHEAD")
        x = dict(base, published_at="2026-11-11T12:00:00Z")
        self.assertEqual(validate_record(x,"2026-11-11T13:00:00Z")["reason"],"NOT_OBSERVED_BY_DECISION")
        self.assertFalse(validate_record(dict(base,published_at=None),"2026-11-11T16:00:00Z")["usable"])

    def test_sec_filing_is_not_known_same_day(self):
        raw={"status":"RAW_AVAILABLE","source_url":"https://data.sec.gov/",
             "facts":{"us-gaap":{"NetIncomeLoss":{"units":{"USD":[
                 {"filed":"2026-11-11","end":"2026-09-30","val":20,"form":"10-Q"},
                 {"filed":"2026-08-01","end":"2026-06-30","val":10,"form":"10-Q"}]}}}}}
        self.assertEqual(len(sec_gaap_facts(raw,"NetIncomeLoss","2026-11-11")),1)
        self.assertEqual(len(sec_gaap_facts(raw,"NetIncomeLoss","2026-11-12")),2)

    def test_cboe_valid_csv(self):
        payload=b"DATE,OPEN,HIGH,LOW,CLOSE\n11/10/2026,20,22,19,21\n11/11/2026,20,22,19,19\n"
        r=cboe_vix("2026-11-10",lambda _: MockResponse(payload))
        self.assertEqual(r["latest"]["vix"],21)
        self.assertEqual(r["quality"],"OBSERVATION_DATE_ONLY_NOT_PIT")

    def test_unconfigured_feeds_are_missing(self):
        self.assertEqual(finra_margin("2026-11-11")["status"],"MISSING")
        self.assertEqual(constituents("2026-11-11")["status"],"MISSING")
        self.assertEqual(tsmc_revenue("2026-11-11")["status"],"MISSING")
        self.assertEqual(valuation_earnings("2026-11-11")["status"],"MISSING")

    def test_constituents_reject_future_and_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"members.json"
            p.write_text(json.dumps({"index":"SOX","effective_date":"2026-11-12",
                                     "symbols":["NVDA","NVDA"],
                                     "source_url":"https://indexes.nasdaq.com/"}))
            self.assertEqual(constituents("2026-11-11",p)["status"],"MISSING")

if __name__ == "__main__":
    unittest.main()
