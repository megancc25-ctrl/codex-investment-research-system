"""Engineering acceptance: synthetic evidence only, never network or credentials."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sentinel.crs import delivery
from sentinel.crs.config import CONFIG_PATH, MODULE_WEIGHTS
from sentinel.crs.engine import score_snapshot
from sentinel.crs.fred import SERIES, fetch_series
from sentinel.crs.market_calendar import latest_completed_xnys_session


class DeliveryTests(unittest.TestCase):
    def test_seven_module_contract_unchanged(self):
        self.assertEqual(MODULE_WEIGHTS, dict(equity=15, rates=15, usd_gold=10,
            credit=20, liquidity=20, real_estate=10, contagion=10))
        self.assertEqual(hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
            delivery.BASELINE_CONFIG_SHA256)
        fixture = delivery.synthetic_collection("2026-11-18")
        result = score_snapshot(fixture["features"], fixture["histories"])
        self.assertEqual(result, delivery.build_report(fixture, "2026-11-19")["research_diagnostics"])

    def test_no_network_or_credential_read_for_blocked_fred(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
             patch("os.environ.get", side_effect=AssertionError("credential read")):
            for key in SERIES:
                with self.assertRaises(PermissionError):
                    fetch_series(key, "2026-11-18")

    def test_default_collection_is_blocked_and_complete(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            report = delivery.build_report(delivery.blocked_collection("2026-11-20"), "2026-11-22")
        self.assertIsNone(report["score_result"]["score"])
        self.assertEqual(len(report["data_status"]["fred"]), 19)
        self.assertTrue(all("LICENSE_BLOCKED" in row["states"] for row in report["data_status"]["fred"].values()))

    def test_dates_are_separate_and_beijing_based(self):
        self.assertEqual(delivery.beijing_date(datetime(2026, 11, 18, 17, tzinfo=timezone.utc)), "2026-11-19")
        report = delivery.build_report(delivery.synthetic_collection("2026-11-18"), "2026-11-19")
        self.assertEqual(report["report_date"], "2026-11-19")
        self.assertEqual(report["observation_date"], "2026-11-18")
        for key in ("retrieved_at", "generated_at", "source", "quality_status", "license_status"):
            self.assertIn(key, report)
        self.assertIsNone(report["score_result"]["score"])
        self.assertEqual(len(report["score_result"]["modules"]), 7)
        self.assertEqual(len(report["alerts"]), 4)

    def test_holiday_and_weekend_do_not_create_observations(self):
        self.assertEqual(latest_completed_xnys_session(datetime(2026, 7, 4, 12, tzinfo=timezone.utc)), "2026-07-02")
        self.assertEqual(latest_completed_xnys_session(datetime(2026, 11, 22, 0, tzinfo=timezone.utc)), "2026-11-20")

    def test_composable_states(self):
        row = delivery.classify_source(license_status="REVIEW_REQUIRED", credential_available=False)
        self.assertEqual(set(row), {"LICENSE_BLOCKED", "CREDENTIAL_MISSING", "SOURCE_UNAVAILABLE"})
        self.assertEqual(delivery.classify_source(license_status="SYNTHETIC", has_value=True, age_days=2, max_age_days=7), ["VALID", "EXPECTED_LAG"])
        self.assertEqual(delivery.classify_source(license_status="SYNTHETIC", has_value=True, age_days=8, max_age_days=7), ["STALE"])
        for error in (TimeoutError(), ConnectionError()):
            self.assertIn("COLLECTION_FAILED", delivery.classify_source(license_status="SYNTHETIC", error=error))

    def test_unapproved_collection_rejected_before_publication(self):
        fixture = delivery.synthetic_collection("2026-11-18")
        fixture["features"]["vix_level"]["license_status"] = "REVIEW_REQUIRED"
        with self.assertRaises(PermissionError):
            delivery.build_report(fixture, "2026-11-19")

    def test_bad_units_future_conflict_and_nonfinite_rejected(self):
        for update in ({"unit": "wrong"}, {"observation_date": "2099-01-01"}, {"value": float("nan")}, {"quality": "CONFLICT"}):
            fixture = delivery.synthetic_collection("2026-11-18")
            fixture["features"]["vix_level"].update(update)
            with self.assertRaises(ValueError):
                delivery.build_report(fixture, "2026-11-19")

    def test_archive_versions_are_immutable_and_searchable(self):
        report = delivery.build_report(delivery.synthetic_collection("2026-11-18"), "2026-11-19")
        with tempfile.TemporaryDirectory() as tmp:
            first = delivery.archive(report, tmp)
            original = Path(first["json"]).read_bytes()
            second = delivery.archive(report, tmp)
            self.assertEqual(Path(first["json"]).name, "2026-11-19.json")
            self.assertEqual(Path(second["json"]).name, "2026-11-19.v2.json")
            self.assertEqual(Path(first["json"]).read_bytes(), original)
            index = json.loads((Path(tmp)/"index.json").read_text())
            self.assertEqual(len(index), 2)
            self.assertTrue(Path(second["html"]).exists())

    def test_three_date_replay_is_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left, right = delivery.replay(a), delivery.replay(b)
            self.assertEqual(len(left), 3)
            for x, y in zip(left, right):
                self.assertEqual(Path(x["json"]).read_bytes(), Path(y["json"]).read_bytes())
                report = json.loads(Path(x["json"]).read_text())
                self.assertEqual(report["quality_status"], "SYNTHETIC_NOT_MARKET_DATA")
                self.assertIsNone(report["score_result"]["score"])
            self.assertIsNone(json.loads(Path(left[0]["json"]).read_text())["changes"]["previous_report"])
            self.assertIsNotNone(json.loads(Path(left[1]["json"]).read_text())["changes"]["previous_report"])

    def test_archive_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            delivery.build_report(delivery.synthetic_collection("2026-11-18"), "../../escape")

    def test_live_price_transport_is_never_called(self):
        from sentinel.crs.prices import fetch_prices
        with patch("yfinance.Ticker", side_effect=AssertionError("network")):
            values, statuses = fetch_prices("2026-11-18")
        self.assertEqual(values, {})
        self.assertTrue(all(x["quality"] == "LICENSE_BLOCKED" for x in statuses.values()))

    def test_all_metrics_have_diagnostic_next_step_and_stale_is_excluded(self):
        fixture = delivery.synthetic_collection("2026-11-18")
        fixture["features"]["vix_level"].update(stale=True, age_days=100)
        report = delivery.build_report(fixture, "2026-11-19")
        self.assertIn("STALE", report["data_status"]["metrics"]["vix_level"]["states"])
        self.assertIsNone(report["research_diagnostics"]["metric_details"]["vix_level"]["value"])
        self.assertTrue(all("next_step" in x for x in report["data_status"]["metrics"].values()))

    def test_archive_rejects_live_payload_before_writing(self):
        report = delivery.build_report(delivery.synthetic_collection("2026-11-18"), "2026-11-19")
        report["research_diagnostics"]["metric_details"]["vix_level"]["license_status"] = "RESTRICTED"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                delivery.archive(report, tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_legacy_writer_does_not_publish_unapproved_values(self):
        from sentinel.crs.report import _public_copy
        report = {"score_result": {"score": 44, "metric_details": {
            "vix_level": {"value": 44, "license_status": "REVIEW_REQUIRED"}}}}
        public = _public_copy(report)
        self.assertIsNone(public["score_result"]["metric_details"]["vix_level"]["value"])
        self.assertIsNone(public["score_result"]["score"])


    def test_parallel_archive_contention_is_explicit(self):
        report = delivery.build_report(delivery.synthetic_collection("2026-11-18"), "2026-11-19")
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp)/".archive.lock"
            lock.write_text("another writer")
            with self.assertRaisesRegex(RuntimeError, "busy"):
                delivery.archive(report, tmp)
            self.assertEqual(lock.read_text(), "another writer")

    def test_permission_block_never_uses_old_real_cache(self):
        from sentinel.crs.collector import collect
        result = collect("2026-11-18", fred_cache={"ust10y": {"values": {"2026-11-17": 4.0}}})
        self.assertEqual(result["fred"], {})
        self.assertEqual(result["prices"], {})

    def test_timezone_naive_and_future_report_inputs_rejected(self):
        with self.assertRaises(ValueError):
            delivery.beijing_date(datetime(2026, 11, 18))
        with self.assertRaises(ValueError):
            delivery.build_report(delivery.synthetic_collection("2026-11-20"), "2026-11-19")


if __name__ == "__main__":
    unittest.main()
