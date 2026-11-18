import json
import tempfile
import unittest
from datetime import date
from urllib.error import HTTPError
from pathlib import Path

from sentinel.crs.collector import collect
from sentinel.crs.fred import fetch_series
from sentinel.crs.health import save_health_snapshot, summarize_source_health
from sentinel.crs.report import write_reports
from sentinel.crs.storage import connect, load_fred_cache, save_collected


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class CRSPhase8Tests(unittest.TestCase):
    def test_fred_fetch_retries_once_and_uses_historical_vintage_api_with_key(self):
        calls, waits = [], []
        payload = json.dumps({"observations": [
            {"date": "2026-11-16", "value": "4.12"},
            {"date": "2026-11-18", "value": "4.99"},
        ]}).encode()

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            if len(calls) == 1:
                raise TimeoutError("read timed out")
            return _Response(payload)

        result = fetch_series("ust10y", "2026-11-17", opener=opener, timeout=3,
                              retries=2, api_key="secret-test", sleep=waits.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(waits, [0.25])
        self.assertIn("api.stlouisfed.org/fred/series/observations", calls[0][0])
        self.assertIn("realtime_start=2026-11-17", calls[0][0])
        self.assertEqual(result["values"], {"2026-11-16": 4.12})
        self.assertEqual(result["source_kind"], "FRED_API_VINTAGE_ASOF")
        self.assertNotIn("secret-test", json.dumps(result))

    def test_fred_fetch_fails_after_bounded_retries_without_leaking_key(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise TimeoutError("read timed out")

        with self.assertRaisesRegex(RuntimeError, "2 attempt") as caught:
            fetch_series("ust10y", "2026-11-17", opener=opener, retries=2,
                         api_key="private-key", sleep=lambda _seconds: None)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("private-key", str(caught.exception))

    def test_fred_fetch_retries_rate_limit_response(self):
        calls = []
        payload = b"observation_date,DGS10\n2026-11-17,4.1\n"

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, "rate limited", {}, None)
            return _Response(payload)

        result = fetch_series("ust10y", "2026-11-17", opener=opener, retries=2,
                              api_key="", sleep=lambda _seconds: None)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["values"], {"2026-11-17": 4.1})

    def test_collector_uses_fresh_cache_after_isolated_fred_failure(self):
        cached = {"ust10y": {"series_key": "ust10y", "series_id": "DGS10",
            "values": {"2026-11-17": 4.1}, "observation_date": "2026-11-17",
            "source": "https://fred.stlouisfed.org/series/DGS10", "source_kind": "FRED_CURRENT_VINTAGE_CSV",
            "quality": "CURRENT_VINTAGE", "license_status": "REVIEW_REQUIRED",
            "retrieved_at": "2026-11-17T23:00:00+00:00", "raw_sha256": "a" * 64,
            "cached": True, "cache_age_days": 0, "cache_max_age_days": 14}}

        def fail(key, asof):
            raise TimeoutError("source timed out")

        result = collect("2026-11-18", fred_fetcher=fail, fred_cache=cached,
                         price_fetcher=lambda _asof: ({}, {}))
        self.assertEqual(result["source_status"]["fred:ust10y"]["status"], "AVAILABLE_CACHED")
        self.assertEqual(result["source_status"]["fred:ust10y"]["fetch_status"], "FAILED")
        self.assertEqual(result["fred"]["ust10y"]["values"]["2026-11-17"], 4.1)
        self.assertIn("timed out", result["source_status"]["fred:ust10y"]["reason"])

    def test_duckdb_cache_round_trip_only_returns_fresh_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = connect(Path(tmp) / "crs.duckdb")
            try:
                save_collected(con, {"asof": "2026-11-18", "fred": {"ust10y": {
                    "series_id": "DGS10", "values": {"2026-11-17": 4.1},
                    "source": "https://fred.stlouisfed.org/series/DGS10",
                    "source_kind": "FRED_CURRENT_VINTAGE_CSV", "quality": "CURRENT_VINTAGE",
                    "license_status": "REVIEW_REQUIRED", "published_at": None,
                    "retrieved_at": "2026-11-17T20:00:00+00:00", "raw_sha256": "a" * 64}},
                    "prices": {}, "features": {}})
                cache = load_fred_cache(con, "2026-11-18")
                self.assertEqual(cache["ust10y"]["values"], {"2026-11-17": 4.1})
                self.assertEqual(cache["ust10y"]["cache_age_days"], 1)
                self.assertNotIn("ust10y", load_fred_cache(con, "2026-12-10"))
            finally:
                con.close()

    def test_fred_api_vintages_keep_separate_asof_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = connect(Path(tmp) / "crs.duckdb")
            try:
                for vintage, value in (("2022-01-03", 1.5), ("2022-01-04", 1.6)):
                    item = {"series_id": "DGS10", "values": {"2022-01-03": value},
                        "source": "https://fred.stlouisfed.org/series/DGS10",
                        "source_kind": "FRED_API_VINTAGE_ASOF", "vintage_date": vintage,
                        "quality": "CURRENT_VINTAGE", "license_status": "REVIEW_REQUIRED",
                        "published_at": None, "retrieved_at": vintage + "T23:00:00+00:00",
                        "raw_sha256": vintage.replace("-", "") * 2}
                    save_collected(con, {"asof": vintage, "fred": {"ust10y": item},
                                     "prices": {}, "features": {}})
                rows = con.execute("SELECT vintage_date, value FROM crs_fred_vintages ORDER BY vintage_date").fetchall()
                self.assertEqual(rows, [(date(2022, 1, 3), 1.5), (date(2022, 1, 4), 1.6)])
            finally:
                con.close()

    def test_source_health_tracks_success_timeouts_lag_and_release_timestamp_gaps(self):
        snapshots = [
            {"asof": "2026-11-16", "source_status": {"fred:ust10y": {
                "status": "AVAILABLE", "observation_date": "2026-11-13", "published_at": None,
                "quality": "CURRENT_VINTAGE", "license_status": "REVIEW_REQUIRED"}}},
            {"asof": "2026-11-17", "source_status": {"fred:ust10y": {
                "status": "MISSING", "reason": "read timed out", "quality": "MISSING"}}},
        ]
        current = {"fred:ust10y": {"status": "AVAILABLE_CACHED", "fetch_status": "FAILED",
            "cache_used": True, "reason": "read timed out", "observation_date": "2026-11-13",
            "published_at": None, "quality": "CURRENT_VINTAGE", "license_status": "REVIEW_REQUIRED"}}
        result = summarize_source_health(snapshots, "2026-11-18", current)["sources"]["fred:ust10y"]
        self.assertEqual(result["window_runs"], 3)
        self.assertEqual(result["live_success_rate_pct"], 33.3)
        self.assertEqual(result["cache_uses"], 1)
        self.assertEqual(result["timeouts"], 2)
        self.assertEqual(result["consecutive_failures"], 2)
        self.assertEqual(result["observation_lag_days"], 5)
        self.assertEqual(result["published_at_missing_rate_pct"], 100.0)

    def test_health_snapshot_replaces_duplicate_asof_and_keeps_only_status_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source_health.json"
            save_health_snapshot(path, "2026-11-17", {"fred:x": {"status": "MISSING"}})
            save_health_snapshot(path, "2026-11-17", {"fred:x": {"status": "AVAILABLE"}})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["source_status"]["fred:x"]["status"], "AVAILABLE")
            self.assertNotIn("values", path.read_text(encoding="utf-8"))

    def test_source_health_is_preserved_in_json_markdown_and_html(self):
        report = {"asof": "2026-11-18", "generated_at": "2026-11-18T00:00:00+00:00",
            "score_result": {"score": None, "status": "DATA_INSUFFICIENT", "data_coverage_pct": 0,
                "data_confidence": "LOW", "metric_coverage_pct": 0, "group_coverage_pct": 0,
                "weighted_module_coverage_pct": 0, "critical_metrics_missing": [],
                "critical_modules_missing": [], "missing_metrics": [], "modules": {},
                "metric_details": {}, "notes": []},
            "state_machine": {"state": "INSUFFICIENT_DATA", "label": "Insufficient data"},
            "pipeline_status": "PIPELINE_SUCCESS", "score_status": "DATA_INSUFFICIENT",
            "alerts": {}, "evidence": {"supporting": [], "against": [],
                "component_evidence": [], "data_limits": []},
            "source_status": {}, "source_health": {"window_runs_max": 30, "asof": "2026-11-18",
                "sources": {"fred:ust10y": {"window_runs": 2, "live_success_rate_pct": 50.0,
                    "cache_uses": 1, "failures": 1, "timeouts": 1, "consecutive_failures": 1,
                    "observation_lag_days": 3, "published_at_missing_rate_pct": 100.0,
                    "latest_quality": "CURRENT_VINTAGE", "latest_license_status": "REVIEW_REQUIRED",
                    "latest_reason": "read timed out"}}},
            "decision": {"action": "NO_ACTION", "rationale": "Research diagnostic only"}}
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_reports(report, tmp)
            public_json = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
            html = Path(paths["html"]).read_text(encoding="utf-8")
        self.assertEqual(public_json["source_health"]["sources"]["fred:ust10y"]["timeouts"], 1)
        self.assertIn("Rolling source health", markdown)
        self.assertIn("fred:ust10y", markdown)
        self.assertIn("Rolling source health", html)


if __name__ == "__main__":
    unittest.main()
