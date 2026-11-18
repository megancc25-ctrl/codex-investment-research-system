"""CRS report orchestration. Public market data only; personal holdings are a separate local tool."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from . import __version__
from .alerts import evaluate_alerts
from .collector import collect
from .config import CONFIG_SHA256
from .decisions import decision_for_state
from .engine import score_snapshot
from .health import load_health_snapshots, save_health_snapshot, summarize_source_health
from .report import write_reports
from .state import STATE_LABELS, candidate_reasons, candidate_state, transition_state
from .storage import connect, export_parquet, latest_reports, load_fred_cache, save_collected, save_report

def _evidence(score_result, features, alerts):
    supporting, against, component_evidence, data_limits = [], [], [], []
    for name, item in score_result["modules"].items():
        if item["score"] is not None and item["score"] >= 50:
            supporting.append(f"{name} module is elevated at {item['score']:.1f}/100 ({item['coverage_pct']:.0f}% module coverage).")
        elif item["score"] is not None and item["score"] < 25 and item["coverage_pct"] == 100:
            component_evidence.append(f"{name} module is low at {item['score']:.1f}/100 with complete configured group coverage.")
    liquidity = alerts.get("liquidity_crisis", {})
    if not isinstance(liquidity, dict):
        liquidity = {}
    liquidity_state = liquidity.get("state", "UNKNOWN")
    liquidity_clear_claim = (liquidity_state == "CLEAR" and
                             liquidity.get("funding_status") == "NORMAL_CONFIRMED")
    for limit in liquidity.get("data_limits", []):
        if limit not in data_limits:
            data_limits.append(limit)
    if liquidity_state == "RED_CANDIDATE":
        supporting.append("A three-asset sell-off and a funding-side anomaly are both confirmed; the liquidity combination alert is RED_CANDIDATE.")
    elif liquidity_state == "FUNDING_STRESS_ONLY":
        supporting.append("A funding-side stress flag is confirmed without a simultaneous three-asset sell-off; the combined liquidity-crisis rule is not met.")
    elif liquidity_state == "CROSS_ASSET_SELL_OFF":
        if liquidity.get("funding_status") == "INSUFFICIENT_DATA" and not liquidity.get("data_limits"):
            missing = liquidity.get("missing_funding_inputs", [])
            if missing:
                data_limits.append("Three-asset sell-off is confirmed, but funding-side inputs are missing: " + ", ".join(missing) + "; the event cannot be classified as a liquidity crisis.")
            else:
                data_limits.append("Three-asset sell-off is confirmed, but repo, funding or margin status is incomplete; the event cannot be classified as a liquidity crisis.")
    elif liquidity_clear_claim:
        pass  # Cross-check the alert against the actual synchronization feature below.
    else:
        if liquidity.get("funding_stress_confirmed"):
            supporting.append("A funding-side anomaly is confirmed, but the available cross-asset synchronization data do not establish the combined liquidity-crisis condition.")
        if not liquidity.get("data_limits"):
            data_limits.append(f"Liquidity status {liquidity_state} does not establish that both cross-asset and funding conditions are normal.")
    credit_alert = alerts.get("credit_risk")
    credit_state = credit_alert.get("state", "UNKNOWN") if isinstance(credit_alert, dict) else "MISSING"
    if credit_state == "CLEAR":
        component_evidence.append("Credit risk combination alert is clear on the available HY/IG spread and equity inputs.")
    elif credit_state == "YELLOW":
        supporting.append("Credit risk combination alert is YELLOW: a watch-level combination is present, but the alert is not confirmed at RED_CANDIDATE level.")
    elif credit_state in ("RED_CANDIDATE", "SEVERE_WATCH"):
        supporting.append(f"Credit risk combination alert is {credit_state}; this is a risk warning, not a validated crisis probability.")
    elif credit_state == "INSUFFICIENT_DATA":
        data_limits.append("Credit risk confirmation is INSUFFICIENT_DATA; missing credit inputs cannot establish either elevated or stable credit risk.")
    else:
        data_limits.append(f"Credit risk alert state {credit_state} is unavailable or unrecognized; no credit-risk conclusion can be drawn.")
    sync = features.get("synchronized_three_asset_down_20d")
    sync_no_selloff_available = False
    if not isinstance(sync, dict):
        data_limits.append("Three-asset synchronization is MISSING; available common dates cannot be assessed.")
    else:
        status = str(sync.get("status") or ("AVAILABLE" if sync.get("value") is not None else "MISSING")).upper()
        if status == "AVAILABLE" and sync.get("value") is True:
            supporting.append("A simultaneous 20-day decline in stocks, bonds and gold is confirmed on aligned common dates.")
        elif status == "AVAILABLE" and sync.get("value") is False:
            component_evidence.append("No simultaneous 20-day decline in stocks, bonds and gold was confirmed within the valid aligned common-date sample.")
            sync_no_selloff_available = True
        elif status == "INSUFFICIENT_DATA":
            data_limits.append("Three-asset synchronization is INSUFFICIENT_DATA; the common-date sample is too short to determine whether a simultaneous decline occurred.")
        else:
            data_limits.append("Three-asset synchronization is MISSING; available common dates cannot be assessed.")
    if liquidity_clear_claim and sync_no_selloff_available:
        against.append("No simultaneous three-asset sell-off was confirmed and all configured repo, funding and margin event flags were explicitly reported normal.")
    elif liquidity_clear_claim:
        data_limits.append("Liquidity alert reports CLEAR, but no matching AVAILABLE=false synchronization feature was supplied; overall counter-evidence is withheld.")
    return {"supporting": supporting, "against": against,
            "component_evidence": component_evidence, "data_limits": data_limits}

def run_report(asof, database, output, parquet_directory=None, manual=None,
               emergency_market_failure=False, nq_report=None, state_history_file=None):
    con = connect(database)
    try:
        fred_cache = load_fred_cache(con, asof)
        collection = collect(asof, fred_cache=fred_cache) if fred_cache else collect(asof)
    except Exception:
        con.close()
        raise
    if manual:
        collection["features"].update(manual["features"])
        collection["source_status"].update(manual["source_status"])
        for key, evidence in manual.get("event_evidence", {}).items():
            collection["source_status"][f"manual_event:{key}"] = {
                **evidence, "status": "AVAILABLE", "source_id": key,
            }
    event_flags = manual.get("events", {}) if manual else {}
    emergency_market_failure = emergency_market_failure or bool(event_flags.get("funding_market_failure"))
    try:
        save_collected(con, collection)
        score = score_snapshot(collection["features"], collection["histories"])
        history = latest_reports(con, limit=10)
        state_file = Path(state_history_file) if state_history_file else None
        if state_file and state_file.exists():
            try:
                state_history = json.loads(state_file.read_text(encoding="utf-8"))
                history = [x for x in state_history if x.get("asof", "") < asof]
            except (ValueError, OSError):
                history = []
        else:
            history = [x for x in history if x.get("asof", "") < asof]
        health_path = Path(database).expanduser().parent / "source_health.json"
        health_history = [x for x in load_health_snapshots(health_path) if x.get("asof") != asof]
        source_health = summarize_source_health(health_history, asof, collection["source_status"])
        save_health_snapshot(health_path, asof, collection["source_status"])
        candidate = candidate_state(score, emergency_market_failure=emergency_market_failure)
        reason_codes = candidate_reasons(score, emergency_market_failure=emergency_market_failure)
        state = transition_state(candidate, history,
                                 emergency_market_failure=emergency_market_failure,
                                 candidate_reason_codes=reason_codes, asof=asof)
        state["transition_evidence"] = {
            "asof": asof, "raw_candidate": candidate, "reason_codes": reason_codes,
            "module_scores": {k: v.get("score") for k, v in score["modules"].items()},
            "trigger_modules": [k for k, v in score["modules"].items()
                                if v.get("score") is not None and v["score"] >= 50],
            "metric_coverage_pct": score.get("metric_coverage_pct"),
            "group_coverage_pct": score.get("group_coverage_pct"),
            "weighted_module_coverage_pct": score.get("weighted_module_coverage_pct"),
        }
        state["label"] = STATE_LABELS.get(state["state"], state["state"])
        alerts = evaluate_alerts(collection["features"], event_flags)
        report = {
            "schema_version": "crs-report-1.0", "crs_version": __version__,
            "config_sha256": CONFIG_SHA256,
            "pipeline_status": "PIPELINE_SUCCESS",
            "score_status": "SCORE_PUBLISHED" if score["score"] is not None else "DATA_INSUFFICIENT",
            "asof": asof, "generated_at": datetime.now(timezone.utc).isoformat(),
            "score_result": score, "state_machine": state, "alerts": alerts,
            "decision": decision_for_state(state["state"]),
            "evidence": _evidence(score, collection["features"], alerts),
            "source_status": collection["source_status"],
            "source_health": source_health,
            "source_count": {"expected_fred_series": sum(k.startswith("fred:") for k in collection["source_status"]),
                             "available_features": len(collection["features"])},
            "integration": {
                "nq_sentinel": "SEPARATE_ENGINE; no NQ-Sentinel score or weights are modified or combined.",
                "nq_report_reference": nq_report,
                "personal_portfolio": "NOT_LOADED; run local_crs_portfolio.py locally if desired.",
            },
            "limitations": [
                "All thresholds and weights are provisional and have not been optimized or validated.",
                "FRED current-vintage data do not provide historical publication vintages for a valid crisis backtest.",
                "Yahoo market prices are unverified proxies; IEF/GLD/DXY are not direct full-market benchmarks.",
                "No automatic order, position-size or FX instruction is generated.",
            ],
        }
        save_report(con, report)
        if state_file:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_history = history + [{"asof": asof, "state": state["state"],
                                        "raw_candidate": state["raw_candidate"],
                                        "candidate_reason_codes": state["candidate_reason_codes"],
                                        **state["transition_evidence"],
                                        "confirmation_gap_days": state.get("confirmation_gap_days"),
                                        "confirmation_basis": state.get("confirmation_basis")}]
            state_file.write_text(json.dumps(state_history[-10:], indent=2) + "\n", encoding="utf-8")
        if parquet_directory:
            export_parquet(con, parquet_directory)
        paths = write_reports(report, output)
        return report, paths
    finally:
        con.close()
