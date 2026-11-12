import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from sentinel.fred_credit_pipeline import SERIES,parse_csv,compute,run

class Response:
    def __init__(self,payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n=-1): return self.payload

def opener(req):
    series=req.full_url.split("=")[-1]
    rows=["observation_date,"+series]
    for i in range(100):
        rows.append(f"2026-01-{(i%28)+1:02d},{i+1}")
    # use actual unique dates
    from datetime import date,timedelta
    rows=["observation_date,"+series]
    for i in range(100):
        rows.append(f"{date(2026,1,1)+timedelta(days=i)},{1+i/100:.3f}")
    return Response(("\n".join(rows)+"\n").encode())

class FredCreditTests(unittest.TestCase):
    def test_expanding_rank_excludes_current(self):
        from datetime import date,timedelta
        h={str(date(2026,1,1)+timedelta(days=i)):float(i) for i in range(100)}
        rows=compute(h,"2026-04-10")
        self.assertEqual(rows[0]["prior_observations"],60)
        self.assertEqual(rows[0]["expanding_risk_percentile"],100)
        self.assertEqual(rows[0]["change_20obs_pct_points"],20)
        self.assertEqual(len(rows),40)

    def test_future_values_do_not_change_past(self):
        from datetime import date,timedelta
        h={str(date(2026,1,1)+timedelta(days=i)):float(i) for i in range(100)}
        cutoff="2026-03-31"
        original=compute(h,cutoff)
        h["2026-04-10"]=999999
        self.assertEqual(compute(h,cutoff),original)

    def test_duplicate_and_bad_values(self):
        series=SERIES["hy_oas"]
        raw=("observation_date,"+series+"\n2026-01-01,1\n2026-01-01,2\n").encode()
        with self.assertRaises(ValueError): parse_csv(raw,series)
        raw=("observation_date,"+series+"\n2026-01-01,-1\n").encode()
        with self.assertRaises(ValueError): parse_csv(raw,series)

    def test_full_pipeline_writes_recomputable_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            result=run("2026-04-10",d,opener)
            self.assertTrue(result["all_three_available"])
            self.assertTrue(result["all_three_with_factor_rows"])
            self.assertEqual(result["factor_rows"],120)
            self.assertEqual(result["pit_status"],"CURRENT_VINTAGE_ONLY_NOT_HISTORICAL_PIT_VERIFIED")
            self.assertEqual(result["full_credit_financing_module"],"MISSING_FINRA")
            with (Path(d)/"fred_credit_factors.csv").open() as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),120)
            for item in result["series"].values():
                raw=(Path(d)/item["raw_file"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),item["raw_sha256"])

    def test_missing_source_never_fabricated(self):
        def bad(req):
            if "BAMLC0A0CM" in req.full_url:
                raise OSError("offline")
            return opener(req)
        with tempfile.TemporaryDirectory() as d:
            result=run("2026-04-10",d,bad)
            self.assertFalse(result["all_three_available"])
            self.assertIn("ig_oas",result["errors"])

if __name__=="__main__": unittest.main()
