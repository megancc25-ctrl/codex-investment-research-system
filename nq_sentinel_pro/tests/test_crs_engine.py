import json, tempfile, unittest
from unittest.mock import patch
from datetime import date, timedelta
from pathlib import Path

from sentinel.crs.config import GROUPS, MODULE_WEIGHTS, RULES
from sentinel.crs.engine import score_snapshot, threshold_score, percentile_risk
from sentinel.crs.state import candidate_state, transition_state
from sentinel.crs.alerts import evaluate_alerts
from sentinel.crs.backtest import evaluate_crisis_backtest
from sentinel.crs.fred import parse_fred_csv
from sentinel.crs.metrics import build_features
from sentinel.crs.manual import load_manual_evidence
from sentinel.crs.report import write_reports
from sentinel.crs.storage import connect, save_report, latest_reports, export_parquet
from sentinel.crs.runner import run_report
from sentinel.risk_v2 import WEIGHTS as NQ_WEIGHTS

def record(value, quality="CURRENT_VINTAGE"):
    return {"value": value, "quality": quality, "source": "fixture", "stale": False, "age_days": 0}

def full_features(risk=False):
    values = {
        "ndx_below_200dma": False, "ndx_gap_below_200dma":0.0, "ndx_drawdown_63d": 0.0, "vix_level": 10.0,
        "breadth_above_200dma": 0.7,
        "ust10y_change_20d_bp": 0.0, "real10y_change_20d_bp": 0.0, "move_level": 90.0,
        "usd_20d_change_pct": 0.0, "gold_drawdown_20d": 0.0,
        "hy_oas_bp": 300.0, "hy_oas_change_20d_bp": 0.0,
        "nfci_level": -0.2, "sofr_iorb_gap_bp": 0.0, "repo_rate_percentile": 50.0,
        "fed_reserves_change_4w_pct": 0.0,
        "real_home_price_yoy_pct": 2.0, "home_sales_yoy_pct": 0.0,
        "stock_bond_corr_20d": 0.0, "synchronized_three_asset_down_20d": False,
    }
    if risk:
        values.update({
            "ndx_below_200dma": True, "ndx_gap_below_200dma":0.20, "ndx_drawdown_63d": 0.20, "vix_level": 45.0,
            "breadth_above_200dma": 0.1,
            "ust10y_change_20d_bp": 80.0, "real10y_change_20d_bp": 55.0, "move_level": 200.0,
            "usd_20d_change_pct": 0.06, "gold_drawdown_20d": 0.2,
            "hy_oas_bp": 900.0, "hy_oas_change_20d_bp": 250.0,
            "nfci_level": 1.2, "sofr_iorb_gap_bp": 60.0, "repo_rate_percentile": 99.5,
            "fed_reserves_change_4w_pct": -20.0,
            "real_home_price_yoy_pct": -12.0, "home_sales_yoy_pct": -40.0,
            "stock_bond_corr_20d": 0.9, "synchronized_three_asset_down_20d": True,
            "synchronized_three_asset_loss_5pct": True,
        })
    return {k: record(v) for k,v in values.items()}

class CRSEngineTests(unittest.TestCase):
    def test_weights_sum_to_one_hundred_and_nq_weights_unchanged(self):
        self.assertEqual(sum(MODULE_WEIGHTS.values()), 100)
        self.assertEqual(NQ_WEIGHTS, {
            "semiconductor_fundamentals": 25, "trend_breadth": 25,
            "credit_financing": 20, "liquidity_leverage": 15,
            "valuation_earnings": 10, "sentiment_options": 5})

    def test_thresholds_and_low_polarity(self):
        self.assertEqual(threshold_score("hy_oas_bp", 500), 50)
        self.assertEqual(threshold_score("hy_oas_bp", 801), 100)
        self.assertEqual(threshold_score("real_home_price_yoy_pct", -6), 75)
        self.assertEqual(threshold_score("real_home_price_yoy_pct", 2), 0)

    def test_missing_inputs_are_not_zero_and_critical_gate_blocks(self):
        result = score_snapshot({})
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertEqual(set(result["critical_modules_missing"]), {"credit", "liquidity"})
        self.assertEqual(result["data_coverage_pct"], 0.0)
        self.assertIsNone(result["modules"]["credit"]["score"])

    def test_manual_funding_failure_forces_emergency_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_collect(asof):
                return {"asof": asof, "fred": {}, "prices": {}, "features": {}, "histories": {},
                        "source_status": {}, "expected_market_proxies": []}
            with patch("sentinel.crs.runner.collect", side_effect=fake_collect):
                report, _ = run_report("2026-11-18", str(Path(tmp)/"db.duckdb"), Path(tmp)/"out",
                    parquet_directory=None, manual={"features": {}, "source_status": {},
                    "events": {"funding_market_failure": True}})
            self.assertEqual(report["state_machine"]["state"], "L4")
            self.assertEqual(report["state_machine"]["transition"], "EMERGENCY_OVERRIDE")

    def test_complete_coverage_produces_research_only_score(self):
        result = score_snapshot(full_features())
        self.assertEqual(result["data_coverage_pct"], 100)
        self.assertEqual(result["status"], "RESEARCH_ONLY_UNVALIDATED")
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["score_is_probability"])

    def test_group_cap_prevents_correlated_metrics_stacking(self):
        features = full_features()
        features["ndx_drawdown_63d"] = record(0.11)
        features["sox_drawdown_63d"] = record(0.16)
        result = score_snapshot(features)
        self.assertEqual(result["modules"]["equity"]["group_scores"]["drawdown"], 75)

    def test_percentile_uses_only_passed_history_and_blends_60_40(self):
        history = [0.0] * 251 + [50.0]
        pct = percentile_risk(history, 30.0, "high")
        self.assertGreater(pct, 95)
        self.assertEqual(percentile_risk([1,2,3], 100, "high"), None)
        result = score_snapshot({"vix_level": record(30)}, {"vix_level": history})
        self.assertAlmostEqual(result["metric_details"]["vix_level"]["score"], 0.6*75 + 0.4*pct, places=2)

    def test_weighted_score_is_100_for_every_extreme_module(self):
        result = score_snapshot(full_features(risk=True))
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["data_coverage_pct"], 100)

    def test_partial_coverage_gate_does_not_publish_score(self):
        features = full_features()
        features.pop("stock_bond_corr_20d")
        features.pop("synchronized_three_asset_down_20d")
        features.pop("move_level")
        features.pop("breadth_above_200dma")
        result = score_snapshot(features)
        self.assertLess(result["data_coverage_pct"], 85)
        self.assertIsNone(result["score"])

    def test_state_upgrade_confirmation_deescalation_and_emergency(self):
        hot = score_snapshot(full_features(risk=True))
        raw = candidate_state(hot)
        self.assertEqual(raw, "L3")
        first = transition_state(raw, [])
        self.assertEqual(first["state"], "L0")
        second = transition_state(raw, [{"state":"L0","raw_candidate":"L3"}])
        self.assertEqual(second["state"], "L3")
        pending = transition_state("L0", [{"state":"L3","raw_candidate":"L0"}])
        self.assertEqual(pending["state"], "L3")
        hist = [{"state":"L3","raw_candidate":"L0"} for _ in range(4)]
        self.assertEqual(transition_state("L0", hist)["state"], "L0")
        self.assertEqual(transition_state("INSUFFICIENT_DATA", hist)["state"], "INSUFFICIENT_DATA")
        self.assertEqual(transition_state("INSUFFICIENT_DATA", [], emergency_market_failure=True)["state"], "L4")

    def test_liquidity_alert_requires_both_sync_selloff_and_funding_stress(self):
        f = {"stock_return_20d":record(-0.1), "bond_return_20d":record(-0.06), "gold_return_20d":record(-0.08)}
        alert = evaluate_alerts(f, {})
        self.assertEqual(alert["liquidity_crisis"]["state"], "CROSS_ASSET_SELL_OFF")
        alert = evaluate_alerts(f, {"repo_extreme":True})
        self.assertEqual(alert["liquidity_crisis"]["state"], "RED_CANDIDATE")
        self.assertTrue(alert["liquidity_crisis"]["severe_synchronized_loss"])

    def test_missing_ai_satellite_data_is_explicit(self):
        alert = evaluate_alerts({}, {})
        self.assertEqual(alert["ai_capital_return"]["state"], "INSUFFICIENT_DATA")
        self.assertFalse(alert["ai_capital_return"]["adds_to_crs_score"])
        self.assertIn("gpu_rental_price_yoy_pct", alert["ai_capital_return"]["missing_inputs"])

    def test_fred_oas_series_is_kept_in_source_units_before_conversion(self):
        parsed = parse_fred_csv(b"observation_date,BAMLH0A0HYM2\n2026-11-17,3.34\n", "BAMLH0A0HYM2")
        self.assertEqual(parsed["2026-11-17"], 3.34)

    def test_fred_feature_changes_convert_percentage_points_to_basis_points(self):
        fred = {}
        base = date(2026, 1, 1)
        hy, ig, nfci, sofr, iorb, reserves = {}, {}, {}, {}, {}, {}
        prices = {k:{} for k in ("ndx","sox","bond_total_return_proxy","gold_proxy")}
        for i in range(70):
            day = (base + timedelta(days=i)).isoformat()
            hy[day] = 3.0 if i < 50 else 4.5
            ig[day] = 1.2
            nfci[day] = -0.1
            sofr[day] = 4.5
            iorb[day] = 4.4
            reserves[day] = 100.0 - i*0.2
            for symbol, multiplier in (("ndx",1.0),("sox",1.5),("bond_total_return_proxy",0.8),("gold_proxy",1.2)):
                prices[symbol][day] = 100 + i*multiplier
        for key, values, sid in (("hy_oas",hy,"HY"),("ig_oas",ig,"IG"),("nfci",nfci,"NFCI"),
                                 ("sofr",sofr,"SOFR"),("iorb",iorb,"IORB"),("reserves",reserves,"RES")):
            fred[key] = {"values":values,"source":sid,"quality":"CURRENT_VINTAGE"}
        features, histories = build_features(prices, fred, "2026-03-11")
        self.assertEqual(features["hy_oas_bp"]["value"], 450)
        self.assertEqual(features["hy_oas_change_20d_bp"]["value"], 150)
        self.assertAlmostEqual(features["sofr_iorb_gap_bp"]["value"], 10)
        self.assertIn("fed_reserves_change_4w_pct", features)
        self.assertLessEqual(len(histories["hy_oas_bp"]), 70)

    def test_backtest_requires_point_in_time_proof(self):
        result = evaluate_crisis_backtest([{"date":"2020-01-01","score":90,"coverage_pct":100,"pit_verified":False}],
                                          [{"start":"2020-02-01","end":"2020-03-01"}])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["metrics"])

    def test_backtest_counts_event_detection_only_for_verified_complete_scores(self):
        rows = []
        start = date(2020,1,1)
        for i in range(80):
            rows.append({"date":(start+timedelta(days=i)).isoformat(),
                         "score":70 if i == 40 else 10, "coverage_pct":100, "pit_verified":True})
        result = evaluate_crisis_backtest(rows,[{"name":"event","start":"2020-02-15","end":"2020-02-25"}],lead_days=20)
        self.assertEqual(result["status"], "DESCRIPTIVE_ONLY")
        self.assertEqual(result["detected_events"], 1)
        self.assertEqual(result["missed_events"], 0)

    def test_manual_evidence_rejects_missing_publication_time_and_future_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"manual.json"
            payload = {"asof":"2026-11-18","features":{"move_level":{
                "value":150,"observation_date":"2026-11-18","published_at":"2026-11-18T20:00:00Z",
                "retrieved_at":"2026-11-18T21:00:00Z","source_url":"https://example.org","quality":"VERIFIED"}}}
            path.write_text(json.dumps(payload),encoding="utf-8")
            self.assertEqual(load_manual_evidence(path,"2026-11-18")["features"]["move_level"]["value"],150)
            del payload["features"]["move_level"]["published_at"]
            path.write_text(json.dumps(payload),encoding="utf-8")
            with self.assertRaises(KeyError):
                load_manual_evidence(path,"2026-11-18")

    def test_reports_redact_licensed_values_and_write_three_formats(self):
        report = {"asof":"2026-11-18","generated_at":"2026-11-18T22:00:00+00:00",
                  "score_result":{"score":None,"status":"INSUFFICIENT_DATA","data_coverage_pct":50,
                    "data_confidence":"LOW","critical_modules_missing":["credit"],"missing_metrics":[],
                    "modules":{m:{"weight_pct":w,"score":None,"coverage_pct":0,"status":"MISSING"}
                               for m,w in MODULE_WEIGHTS.items()},
                    "metric_details":{"hy_oas_bp":{"quality":"LICENSE_RESTRICTED","value":550}},
                    "notes":[]},
                  "state_machine":{"state":"INSUFFICIENT_DATA","label":"INSUFFICIENT_DATA"},
                  "alerts":{},"decision":{"action":"NO_POSITION_ACTION","rationale":"missing",
                    "human_approval_required":True},"evidence":{"supporting":[],"against":[]},
                  "source_status":{}}
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_reports(report,tmp)
            public = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertIsNone(public["score_result"]["metric_details"]["hy_oas_bp"]["value"])
            self.assertTrue(public["report_data_policy"]["licensed_metric_values_redacted"])
            self.assertTrue(Path(paths["markdown"]).exists())
            self.assertTrue(Path(paths["html"]).exists())

    def test_duckdb_round_trip_and_parquet_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = connect(Path(tmp)/"crs.duckdb")
            payload = {"asof":"2026-11-18","generated_at":"2026-11-18T22:00:00+00:00",
                       "score_result":{"score":25,"status":"RESEARCH_ONLY_UNVALIDATED"},
                       "state_machine":{"state":"L1"}}
            save_report(con,payload)
            self.assertEqual(latest_reports(con)[0]["state_machine"]["state"],"L1")
            export_parquet(con,Path(tmp)/"parquet")
            self.assertTrue((Path(tmp)/"parquet"/"crs_reports.parquet").exists())
            con.close()

    def test_local_private_overlay_calculates_only_user_supplied_stress(self):
        from local_crs_portfolio import calculate_stress, write_obsidian
        profile = {"max_loss_budget_pct":0.10,
                   "assets":[{"asset_class":"equity","weight":0.6},{"asset_class":"bond","weight":0.4}],
                   "stress_scenarios":[{"name":"test","returns_by_asset_class":{"equity":-0.2,"bond":-0.1}}]}
        rows = calculate_stress(profile,profile["stress_scenarios"])
        self.assertAlmostEqual(rows[0]["projected_nav_loss_pct"],0.16)
        self.assertAlmostEqual(rows[0]["risk_budget_utilization"],1.6)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio = root/"profile.json"; portfolio.write_text(json.dumps(profile),encoding="utf-8")
            market = root/"market.json"; market.write_text(json.dumps({"asof":"2026-11-18",
                "state_machine":{"state":"L1"},"score_result":{"score":25}}),encoding="utf-8")
            output = write_obsidian(root/"vault",portfolio,market)
            self.assertTrue(output.exists())
            self.assertIn("PRIVATE",output.read_text(encoding="utf-8"))

    def test_end_to_end_runner_with_synthetic_public_fixture(self):
        from unittest.mock import patch
        from sentinel.crs import runner
        source = {}
        collection = {"asof":"2026-11-18","fred":{},"prices":{},
                      "features":full_features(),"histories":{},
                      "source_status":{},"expected_market_proxies":[]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(runner,"collect",return_value=collection):
                report, paths = run_report("2026-11-18",Path(tmp)/"db.duckdb",
                                           Path(tmp)/"reports",Path(tmp)/"parquet")
            self.assertEqual(report["score_result"]["score"],0)
            self.assertTrue(Path(paths["json"]).exists())
            self.assertTrue((Path(tmp)/"parquet"/"crs_features.parquet").exists())

if __name__ == "__main__":
    unittest.main()
