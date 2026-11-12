import unittest
from sentinel.risk_v2 import score_v2, observation, technical_observations, WEIGHTS

class RiskV2Tests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        result = score_v2({})
        self.assertIsNone(result["score"])
        self.assertEqual(result["verified_coverage_pct"], 0)
        self.assertEqual(result["module_details"]["credit_financing"]["status"], "MISSING")

    def test_unverified_proxy_never_publishes_full_score(self):
        signal = {"ndx_vs_200dma": .01, "sox_vs_200dma": -.03,
                  "sox_relative_ndx_20d": -.06, "ndx_20d_realized_vol": .36,
                  "breadth_50dma": 0}
        r = score_v2(technical_observations(signal, "2026-11-11"))
        self.assertIsNone(r["score"])
        self.assertEqual(r["verified_coverage_pct"], 0)
        self.assertEqual(r["coverage_pct"], 30)

    def test_full_verified_and_comparison(self):
        mods = {k: observation(60, "2026-11-11", "test verified fixture")
                for k in WEIGHTS}
        r = score_v2(mods)
        self.assertEqual(r["score"], 60)
        self.assertFalse(r["comparable"])
        prior = {"version": r["version"], "score": 55, "status": "RESEARCH_UNVALIDATED"}
        compared = score_v2(mods, prior)
        self.assertEqual(compared["delta"], 5)

    def test_missing_mandatory_even_with_80pct(self):
        mods = {k: observation(40, "2026-11-11", "fixture")
                for k in WEIGHTS if k != "credit_financing"}
        r = score_v2(mods)
        self.assertIsNone(r["score"])
        self.assertFalse(r["required_verified"])

    def test_bad_values_rejected(self):
        with self.assertRaises(ValueError):
            observation(-1, "2026-11-11", "fixture")
        with self.assertRaises(ValueError):
            score_v2({"fake": observation(20, "2026-11-11", "fixture")})

if __name__ == "__main__":
    unittest.main()
