import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.crs.alerts import evaluate_alerts
from sentinel.crs.engine import score_snapshot
from sentinel.crs.feature_status import read_feature
from sentinel.crs.runner import _evidence
from sentinel.crs.runner import run_report
from sentinel.crs.storage import connect_fred_cache, load_fred_cache, save_fred_cache


def source_record(series_id, license_status, digest="a" * 64, source_url=None):
    return {"series_id": series_id, "values": {"2026-11-17": 4.1},
        "source": source_url or f"https://fred.stlouisfed.org/series/{series_id}",
        "source_kind": "FRED_API_VINTAGE_ASOF", "vintage_date": "2026-11-17",
        "quality": "CURRENT_VINTAGE", "license_status": license_status,
        "cache_authorization": license_status, "published_at": None,
        "retrieved_at": "2026-11-17T20:00:00+00:00", "raw_sha256": digest}


class CRSPhase9Tests(unittest.TestCase):
    def test_shared_feature_status_reader_fails_closed_on_mismatch_and_unknown(self):
        features = {
            "available_false": {"value": False, "status": "AVAILABLE"},
            "missing_false": {"value": False, "status": "MISSING"},
            "insufficient_true": {"value": True, "status": "INSUFFICIENT_DATA"},
            "unknown_true": {"value": True, "status": "SOMETHING_NEW"},
            "available_non_boolean": {"value": 1, "status": "AVAILABLE"},
            "stale_available": {"value": True, "status": "AVAILABLE", "stale": True},
        }
        self.assertEqual(read_feature(features, "available_false"), ("AVAILABLE", False))
        self.assertEqual(read_feature(features, "missing_false"), ("MISSING", None))
        self.assertEqual(read_feature(features, "insufficient_true"), ("INSUFFICIENT_DATA", None))
        self.assertEqual(read_feature(features, "unknown_true"), ("UNKNOWN", None))
        self.assertEqual(read_feature(features, "available_non_boolean", bool), ("UNKNOWN", None))
        self.assertEqual(read_feature(features, "stale_available", bool), ("INSUFFICIENT_DATA", None))

    def test_liquidity_alert_does_not_use_value_when_feature_status_is_not_available(self):
        normal_funding = {"repo_extreme": False, "funding_market_failure": False, "margin_stress": False}
        for status in ("MISSING", "INSUFFICIENT_DATA", "UNKNOWN"):
            with self.subTest(status=status):
                alerts = evaluate_alerts({"synchronized_three_asset_down_20d": {
                    "value": False, "status": status}}, normal_funding)
                self.assertEqual(alerts["liquidity_crisis"]["state"], "INSUFFICIENT_DATA")
                self.assertEqual(alerts["liquidity_crisis"]["synchronized_three_asset_loss"], False)
                self.assertEqual(alerts["liquidity_crisis"]["synchronization_status"], status)
                self.assertTrue(alerts["liquidity_crisis"]["data_limits"])

    def test_available_sync_boolean_still_drives_expected_alert(self):
        alerts = evaluate_alerts({"synchronized_three_asset_down_20d": {
            "value": True, "status": "AVAILABLE"}},
            {"repo_extreme": True, "funding_market_failure": False, "margin_stress": False})
        self.assertEqual(alerts["liquidity_crisis"]["state"], "RED_CANDIDATE")

    def test_runner_evidence_uses_shared_status_and_does_not_claim_no_selloff(self):
        features = {"synchronized_three_asset_down_20d": {"value": False, "status": "MISSING"}}
        alerts = evaluate_alerts(features, {"repo_extreme": False,
            "funding_market_failure": False, "margin_stress": False})
        evidence = _evidence(score_snapshot({}), features, alerts)
        self.assertFalse(any("No simultaneous 20-day decline" in item for item in evidence["component_evidence"]))
        self.assertFalse(any("No simultaneous three-asset sell-off" in item for item in evidence["against"]))
        self.assertTrue(any("MISSING" in item for item in evidence["data_limits"]))

    def test_separate_cloud_cache_rejects_unapproved_restricted_and_bad_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = connect_fred_cache(Path(tmp) / "fred_cache.duckdb")
            try:
                items = {
                    "ust10y": source_record("DGS10", "APPROVED_FOR_INTERNAL_CACHE"),
                    "hy_oas": source_record("BAMLH0A0HYM2", "RESTRICTED"),
                    "cpi": source_record("CPIAUCSL", "REVIEW_REQUIRED"),
                    "vix": source_record("VIXCLS", "APPROVED_FOR_INTERNAL_CACHE", digest="bad"),
                    "sofr": source_record("SOFR", "APPROVED_FOR_INTERNAL_CACHE",
                        source_url="https://not-fred.example/source"),
                }
                saved = save_fred_cache(con, {"asof": "2026-11-18", "fred": items})
                loaded, diagnostics = load_fred_cache(con, "2026-11-18")
                self.assertEqual(saved["saved_series_count"], 1)
                self.assertEqual(saved["ineligible_series_count"], 4)
                self.assertEqual(set(loaded), {"ust10y"})
                self.assertEqual(diagnostics["ineligible_series_count"], 0)
                self.assertEqual(loaded["ust10y"]["cache_authorization"], "APPROVED_FOR_INTERNAL_CACHE")
                con.execute("UPDATE crs_fred_cache SET value = 9.9 WHERE series_key = 'ust10y'")
                corrupted, diagnostics = load_fred_cache(con, "2026-11-18")
                self.assertNotIn("ust10y", corrupted)
                self.assertEqual(diagnostics["ineligible_series_count"], 1)
            finally:
                con.close()

    def test_separate_cloud_cache_excludes_expired_series_and_reports_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = connect_fred_cache(Path(tmp) / "fred_cache.duckdb")
            try:
                save_fred_cache(con, {"asof": "2026-11-18", "fred": {
                    "ust10y": source_record("DGS10", "APPROVED_FOR_INTERNAL_CACHE")}})
                loaded, diagnostics = load_fred_cache(con, "2026-12-10")
                self.assertNotIn("ust10y", loaded)
                self.assertEqual(diagnostics["expired_series_count"], 1)
            finally:
                con.close()

    def test_runner_reports_live_cache_expired_ineligible_and_missing_counts(self):
        day = "2026-11-18"
        collection = {"asof": day, "fred": {
            "ust10y": source_record("DGS10", "REVIEW_REQUIRED")},
            "prices": {}, "features": {}, "histories": {},
            "source_status": {
                "fred:ust10y": {"status": "AVAILABLE", "fetch_status": "SUCCESS"},
                "fred:vix": {"status": "MISSING", "fetch_status": "FAILED", "reason": "timeout"},
            }, "expected_market_proxies": []}
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "crs.duckdb"
            with patch("sentinel.crs.runner.collect", return_value=collection):
                report, paths = run_report(day, str(database), Path(tmp) / "reports")
            summary = report["source_collection_summary"]
            self.assertEqual(summary["fred_expected_count"], 2)
            self.assertEqual(summary["live_success_count"], 1)
            self.assertEqual(summary["cache_fallback_count"], 0)
            self.assertEqual(summary["cache_expired_count"], 0)
            self.assertEqual(summary["cache_ineligible_count"], 1)
            self.assertEqual(summary["missing_count"], 1)
            self.assertTrue((Path(tmp) / "fred_cache.duckdb").exists())
            markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
            self.assertIn("FRED collection and cache counts", markdown)
            self.assertIn("Ineligible cache series: **1**", markdown)


if __name__ == "__main__":
    unittest.main()
