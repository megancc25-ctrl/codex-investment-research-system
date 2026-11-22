"""CRS 1.1 offline delivery boundary; no live sources or credentials admitted."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
import math
from pathlib import Path

from .alerts import evaluate_alerts
from .config import CONFIG_PATH, MODULE_WEIGHTS, RULES
from .engine import score_snapshot
from .fred import SERIES, LICENSE_RESTRICTED
from .market_calendar import latest_completed_xnys_session
from .report import render_markdown
from .runner import _evidence

BASELINE_CONFIG_SHA256 = "5fa0303bab13b8b9f9a270ef043b5b9d7ddb0aa2b980858980be692c678110ad"
BEIJING = timezone(timedelta(hours=8))
# Freshness budgets are engineering defaults, not verified release calendars.
SERIES_META = {
    "hy_oas": ("daily", "percent", 7, "P1"), "ig_oas": ("daily", "percent", 7, "P1"),
    "ccc_oas": ("daily", "percent", 7, "P2"),
    "ust10y": ("daily", "percent", 7, "P0"), "ust30y": ("daily", "percent", 7, "P0"),
    "real10y": ("daily", "percent", 7, "P0"), "vix": ("daily", "index", 7, "P0"),
    "sofr": ("daily", "percent", 7, "P0"), "iorb": ("daily", "percent", 7, "P0"),
    "nfci": ("weekly", "index", 21, "P0"), "reserves": ("weekly", "million USD", 21, "P1"),
    "rrp": ("daily", "billion USD", 7, "P1"), "tga": ("weekly", "million USD", 21, "P1"),
    "broad_usd": ("daily", "index", 14, "P1"), "case_shiller": ("monthly", "index", 120, "P2"),
    "home_sales": ("monthly", "million annualized", 90, "P2"),
    "mortgage30y": ("weekly", "percent", 21, "P2"), "cpi": ("monthly", "index", 75, "P2"),
    "stlfsi": ("weekly", "index", 21, "P1"),
}
OFFICIAL_CANDIDATES = [
    {"owner": "US Treasury", "source": "https://home.treasury.gov/resource-center-data-chart-center/interest-rates",
     "indicators": ["ust10y", "ust30y", "real10y"], "requires_fred_key": False},
    {"owner": "New York Fed", "source": "https://markets.newyorkfed.org/", "indicators": ["sofr"], "requires_fred_key": False},
    {"owner": "Chicago Fed", "source": "https://www.chicagofed.org/research/data/nfci/current-data",
     "indicators": ["nfci"], "requires_fred_key": False},
    {"owner": "Cboe", "source": "https://www.cboe.com/tradable_products/vix/vix_historical_data/",
     "indicators": ["vix"], "requires_fred_key": False},
]


def beijing_date(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return now.astimezone(BEIJING).date().isoformat()


def classify_source(*, license_status, credential_available=None, has_value=False,
                    age_days=0, max_age_days=7, error=None):
    states = []
    if license_status not in ("APPROVED", "SYNTHETIC"):
        states.append("LICENSE_BLOCKED")
    if credential_available is False:
        states.append("CREDENTIAL_MISSING")
    if error is not None:
        states.append("COLLECTION_FAILED")
    if not has_value:
        states.append("SOURCE_UNAVAILABLE")
    elif age_days < 0:
        states.append("COLLECTION_FAILED")
    elif age_days > max_age_days:
        states.append("STALE")
    elif not states:
        states.append("VALID")
        if age_days > 0:
            states.append("EXPECTED_LAG")
    return states


def source_matrix(asof):
    date.fromisoformat(asof)
    result = {}
    for key, series_id in SERIES.items():
        frequency, unit, budget, priority = SERIES_META[key]
        license_status = "RESTRICTED" if key in LICENSE_RESTRICTED else "REVIEW_REQUIRED"
        result[key] = {"series_id": series_id, "source": f"https://fred.stlouisfed.org/series/{series_id}",
            "frequency": frequency, "unit": unit, "priority": priority,
            "freshness_budget_calendar_days": budget, "expected_publication_delay": None,
            "release_calendar_status": "NOT_VERIFIED", "collection_method": "DISABLED",
            "observation_date": None, "retrieved_at": None, "last_success_observation_date": None,
            "license_status": license_status, "quality_status": "NOT_COLLECTED", "allowed_uses": [],
            "status": "LICENSE_BLOCKED", "quality": "NOT_COLLECTED",
            "reason": "No admitted license; no collection attempted. Review owner terms before enabling.",
            "credential_status": "NOT_INSPECTED_NOT_PROVISIONED_FOR_ENGINEERING",
            "states": classify_source(license_status=license_status),
            "missing_reason": "No admitted license; credential state not inspected. No collection attempted.",
            "next_step": "Verify owner terms and separate access, internal use, storage and publication rights before enabling.",
            "alternative": next((x["source"] for x in OFFICIAL_CANDIDATES if key in x["indicators"]), None),
            "proxy_quality": "NOT_ADMITTED"}
    return result


def blocked_collection(asof):
    return {"asof": asof, "features": {}, "histories": {}, "fred": {}, "prices": {},
            "source_status": {}, "synthetic": False}


def synthetic_collection(asof):
    date.fromisoformat(asof)
    # Deterministic artificial values. They are not historical market observations.
    day_number = date.fromisoformat(asof).toordinal() % 3
    features = {}
    for key, (_module, _group, _polarity, levels) in RULES.items():
        value = levels[min(day_number, len(levels)-1)][0]
        if key in ("ndx_below_200dma", "synchronized_three_asset_down_20d", "synchronized_three_asset_loss_5pct"):
            value = bool(day_number)
        features[key] = {"value": value, "source": "synthetic://crs-1.1/v1",
            "quality": "SYNTHETIC", "license_status": "SYNTHETIC", "unit": "feature-native",
            "observation_date": asof, "retrieved_at": asof+"T22:00:00+00:00",
            "age_days": 0, "stale": False}
    return {**blocked_collection(asof), "features": features, "synthetic": True}


def _validate(collection, report_date):
    asof = collection["asof"]
    if date.fromisoformat(asof) > date.fromisoformat(report_date):
        raise ValueError("observation date is after report date")
    if collection.get("fred") or collection.get("prices"):
        raise PermissionError("No live/raw series are admitted in engineering delivery")
    for key, item in collection["features"].items():
        if not collection.get("synthetic") or item.get("license_status") != "SYNTHETIC":
            raise PermissionError("Unapproved input cannot enter report or persistence")
        if item.get("source") != "synthetic://crs-1.1/v1" or item.get("quality") != "SYNTHETIC":
            raise ValueError("Synthetic provenance conflict")
        if key not in RULES or item.get("unit") != "feature-native":
            raise ValueError("Unexpected feature or unit")
        if item.get("observation_date", "9999") > asof:
            raise ValueError("Future observation rejected")
        if not isinstance(item.get("value"), (int, float)) or not math.isfinite(item["value"]):
            raise ValueError("Invalid numeric value")


def build_report(collection, report_date=None, generated_at=None, previous=None):
    report_date = report_date or beijing_date()
    _validate(collection, report_date)
    asof = collection["asof"]
    research = score_snapshot(collection["features"], collection["histories"])
    displayed = deepcopy(research)
    displayed["score"] = None
    displayed["status"] = "MODEL_UNVALIDATED_FORMAL_SCORE_DISABLED"
    synthetic = bool(collection.get("synthetic"))
    alerts = evaluate_alerts(collection["features"], {})
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    report = {"schema_version": "crs-report-1.1", "report_date": report_date,
        "observation_date": asof, "asof": asof,
        "retrieved_at": max((x["retrieved_at"] for x in collection["features"].values()), default=None),
        "generated_at": generated_at, "source": "synthetic://crs-1.1/v1" if synthetic else "NO_LIVE_COLLECTION",
        "quality_status": "SYNTHETIC_NOT_MARKET_DATA" if synthetic else "NO_ADMITTED_DATA",
        "license_status": "SYNTHETIC" if synthetic else "LICENSE_BLOCKED",
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "config_hash_normalization": "LF_LINE_ENDINGS", "pipeline_status": "PIPELINE_SUCCESS",
        "score_status": "FORMAL_SCORE_DISABLED", "score_result": displayed,
        "research_diagnostics": research, "alerts": alerts,
        "state_machine": {"state": "INSUFFICIENT_DATA", "label": "Formal state not approved"},
        "decision": {"action": "NO_POSITION_ACTION", "rationale": "Engineering output only; no investment decision or orders."},
        "evidence": _evidence(displayed, collection["features"], alerts),
        "source_status": source_matrix(asof),
        "data_status": {"fred": source_matrix(asof), "metrics": {
            key: {"module": rule[0], "source": collection["features"].get(key, {}).get("source"),
                "quality_status": collection["features"].get(key, {}).get("quality", "MISSING"),
                "license_status": collection["features"].get(key, {}).get("license_status", "REVIEW_REQUIRED"),
                "states": classify_source(license_status=collection["features"].get(key, {}).get("license_status", "REVIEW_REQUIRED"),
                    has_value=key in collection["features"],
                    age_days=collection["features"].get(key, {}).get("age_days", 0), max_age_days=7),
                "next_step": "Synthetic engineering fixture only" if synthetic else "Admit licensed source, validate unit and release date before collection"}
            for key, rule in RULES.items()},
            "official_candidates": [{**x, "license_status": "NOT_REVIEWED", "collection_enabled": False} for x in OFFICIAL_CANDIDATES]},
        "module_mapping": {"display": "SEVEN_MODULES", "reason": "No lossless six-dimension specification supplied; preserve independent contagion module.",
            "weights_pct": dict(MODULE_WEIGHTS)},
        "real_data_coverage_pct": None,
        "synthetic_metric_coverage_pct": research["data_coverage_pct"] if synthetic else None,
        "changes": {"previous_report": previous.get("report_date") if previous else None,
            "previous_observation_date": previous.get("observation_date") if previous else None,
            "comparison_basis": "previous supplied report; not necessarily previous trading session",
            "module_research_score_delta": {key: round(item["score"] - previous["research_diagnostics"]["modules"][key]["score"], 2)
                if previous and item["score"] is not None and previous["research_diagnostics"]["modules"][key]["score"] is not None else None
                for key, item in research["modules"].items()}},
        "audit": {"mode": "OFFLINE_SYNTHETIC_REPLAY" if synthetic else "BLOCKED_DIAGNOSTIC",
            "live_collection_attempted": False, "credentials_read": False,
            "model_validated": False, "production_trading_changed": False,
            "synthetic_fixture_sha256": hashlib.sha256(json.dumps(collection, sort_keys=True).encode()).hexdigest() if synthetic else None}}
    return report


def _archive_unlocked(report, directory):
    """First file is immutable; reruns use .v2, .v3 ...; index is derived."""
    day = report["report_date"]
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("ISO report date required")
    if report.get("license_status") not in ("SYNTHETIC", "LICENSE_BLOCKED"):
        raise PermissionError("Report not admitted for engineering publication")
    for section in ("score_result", "research_diagnostics"):
        for item in report.get(section, {}).get("metric_details", {}).values():
            if item.get("value") is not None and item.get("license_status") != "SYNTHETIC":
                raise PermissionError("Unapproved metric cannot be archived")
    json.dumps(report, allow_nan=False)  # Fail before reserving any archive path.
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    # Reserve using exclusive create; parallel writers cannot select same version.
    version = 1
    while True:
        stem = day if version == 1 else f"{day}.v{version}"
        path = out / (stem+".json")
        try:
            handle = path.open("x", encoding="utf-8")
            break
        except FileExistsError:
            version += 1
    payload = deepcopy(report)
    payload["archive"] = {"version": version, "policy": "IMMUTABLE_FIRST_AND_NUMBERED_RERUNS"}
    with handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    header = (f"# CRS跨资产风险日报｜{day}\n\n"
        f"Quality: **{payload['quality_status']}**; observation date: {payload['observation_date']}; version: {version}\n\n"
        "Formal score: N/A. Synthetic numbers are engineering examples, not market evidence.\n\n")
    markdown = header + render_markdown(payload)
    html_path = out / (stem+".html")
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>"+html.escape(stem)+
            "</title><body><pre>"+html.escape(markdown)+"</pre></body></html>\n")
    entries = []
    for item in sorted(out.glob("*.json")):
        if item.name == "index.json":
            continue
        saved = json.loads(item.read_text(encoding="utf-8"))
        entries.append({"report_date": saved["report_date"], "observation_date": saved["observation_date"],
            "version": saved["archive"]["version"], "json": item.name, "html": item.with_suffix(".html").name,
            "quality_status": saved["quality_status"]})
    temporary = out / f"index.{stem}.tmp"
    temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    temporary.replace(out/"index.json")
    return {"json": str(path), "html": str(html_path)}


def archive(report, directory):
    """Serialize archive/index writers; contention fails explicitly for retry."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    lock = out / ".archive.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError("Archive is busy or interrupted; inspect .archive.lock before retry") from None
    try:
        with handle:
            return _archive_unlocked(report, out)
    finally:
        lock.unlink()


def replay(directory):
    outputs, previous = [], None
    for report_day, observation in (("2026-11-19", "2026-11-18"), ("2026-11-20", "2026-11-19"), ("2026-11-21", "2026-11-20")):
        report = build_report(synthetic_collection(observation), report_day,
            generated_at=report_day+"T08:00:00+08:00", previous=previous)
        outputs.append(archive(report, directory))
        previous = report
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="CRS 1.1 engineering delivery (no live collection)")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", default="reports/crs")
    parser.add_argument("--report-date")
    args = parser.parse_args(argv)
    if args.replay:
        paths = replay(args.output)
    else:
        day = args.report_date or beijing_date()
        cutoff = datetime.combine(date.fromisoformat(day), datetime.min.time(), BEIJING)+timedelta(hours=8)
        asof = latest_completed_xnys_session(cutoff)
        paths = archive(build_report(blocked_collection(asof), day), args.output)
    print(json.dumps(paths, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
