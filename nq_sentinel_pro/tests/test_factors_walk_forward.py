import unittest
from sentinel.factors_v2 import FACTORS, calculate_modules, expanding_percentile
from sentinel.point_in_time import validate_record
from sentinel.walk_forward_v2 import walk_forward

def evidence(name, published="2026-11-10T21:00:00Z", retrieved="2026-11-12T09:00:00Z", verified=True):
    return {"indicator":name,"value":12.0,"unit":"index",
            "observation_date":"2026-11-10","published_at":published,
            "retrieved_at":retrieved,"source_url":"https://example.org/official",
            "source_kind":"OFFICIAL_FIXTURE","risk_percentile":50.0,
            "history_count":100,"historical_release_verified":verified}

class SixModuleTests(unittest.TestCase):
    def test_no_partial_module_promotion(self):
        m,d=calculate_modules({"hy_ig_ccc_spreads":evidence("hy_ig_ccc_spreads")},
                               "2026-11-12T12:00:00Z")
        self.assertEqual(m,{})
        self.assertEqual(d["credit_financing"]["coverage"],.5)

    def test_complete_six_modules(self):
        records={f:evidence(f) for names in FACTORS.values() for f in names}
        m,d=calculate_modules(records,"2026-11-12T12:00:00Z")
        self.assertEqual(len(m),6)
        self.assertTrue(all(v["coverage"]==1 for v in d.values()))

    def test_historical_retrieval_allowed_only_with_release_proof(self):
        r=evidence("x")
        self.assertEqual(validate_record(r,"2026-11-11T23:59:59Z")["reason"],
                         "NOT_OBSERVED_BY_DECISION")
        self.assertTrue(validate_record(r,"2026-11-11T23:59:59Z",mode="historical")["usable"])
        r["historical_release_verified"]=False
        self.assertEqual(validate_record(r,"2026-11-11T23:59:59Z",mode="historical")["reason"],
                         "UNVERIFIED_HISTORICAL_RELEASE")

    def test_no_future_release(self):
        r=evidence("x",published="2026-11-13T00:00:00Z",retrieved="2026-11-14T09:00:00Z")
        self.assertEqual(validate_record(r,"2026-11-11T23:59:59Z",mode="historical")["reason"],
                         "LOOKAHEAD")

    def test_no_backfilled_scores(self):
        sessions=["2026-11-10","2026-11-11","2026-11-12"]
        result=walk_forward(sessions,{},[100,90,95],horizons=(1,))
        self.assertEqual(result["fully_scored"],0)
        self.assertIsNone(result["rows"][0]["score"])
        self.assertAlmostEqual(result["rows"][0]["future_drawdown"]["1"],-.1)

    def test_expanding_percentile_no_short_history(self):
        self.assertIsNone(expanding_percentile([1,2,3],2))
        self.assertEqual(expanding_percentile([1,2,3],2,minimum=3),200/3)

if __name__=="__main__":
    unittest.main()
