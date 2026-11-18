import json, tempfile, unittest
from pathlib import Path
from local_crs_portfolio import load_profile

class LocalCRSProfileTests(unittest.TestCase):
    def test_rejects_non_summing_weights_and_invalid_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"private.json"
            p.write_text(json.dumps({"assets":[{"asset_class":"equity","weight":0.7}],
                                     "max_loss_budget_pct":0.1}),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile(p)
            p.write_text(json.dumps({"assets":[{"asset_class":"equity","weight":1.0}],
                                     "max_loss_budget_pct":0}),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile(p)

if __name__ == "__main__":
    unittest.main()
