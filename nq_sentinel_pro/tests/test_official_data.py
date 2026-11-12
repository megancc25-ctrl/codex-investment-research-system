import io
import unittest
from sentinel.official_data import fred_csv, fetch_official, official_module_observations
from sentinel.risk_v2 import score_v2

class Response:
    def __init__(self, text):
        self.data = text.encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self):
        return self.data

class OfficialDataTests(unittest.TestCase):
    def test_fred_last_valid_asof(self):
        csv = "observation_date,BAMLH0A0HYM2\n2026-11-09,4.25\n2026-11-10,.\n2026-11-12,7.5\n"
        item = fred_csv("BAMLH0A0HYM2", "2026-11-11", lambda _: Response(csv))
        self.assertEqual(item["value"], 4.25)
        self.assertEqual(item["asof"], "2026-11-09")

    def test_stale_fred_fails_closed(self):
        def opener(url):
            series = url.split("=")[-1]
            return Response(f"observation_date,{series}\n2025-01-01,4.0\n")
        result = fetch_official("2026-11-11", opener)
        self.assertEqual(result["observations"], {})
        self.assertEqual(len(result["errors"]), 9)

    def test_verified_credit_but_not_full_score(self):
        items = {}
        for name, val in (("hy_oas", 4.2), ("ig_oas", 1.2), ("ccc_oas", 9.5)):
            items[name] = {"value": val, "asof": "2026-11-10",
                           "source": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=x"}
        mods = official_module_observations({"observations": items})
        self.assertIn("credit_financing", mods)
        self.assertEqual(mods["credit_financing"]["quality"], "VERIFIED")
        self.assertIsNone(score_v2(mods)["score"])

if __name__ == "__main__":
    unittest.main()
