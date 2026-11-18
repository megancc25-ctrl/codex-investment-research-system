"""Point-in-time crisis backtest metrics. This refuses unsupported label or vintage claims."""
from __future__ import annotations
from datetime import date, datetime, timezone
import re

def _has_pit_evidence(row):
    """Require auditable source metadata; a caller-supplied boolean alone is insufficient."""
    if row.get("pit_verified") is not True or not row.get("pit_evidence"):
        return False
    try:
        decision_at = datetime.fromisoformat(row["decision_at"].replace("Z", "+00:00"))
        if decision_at.tzinfo is None:
            return False
        decision_at = decision_at.astimezone(timezone.utc)
        asof = date.fromisoformat(row["date"])
        if decision_at.date() != asof:
            return False
        for evidence in row["pit_evidence"]:
            published = datetime.fromisoformat(evidence["published_at"].replace("Z", "+00:00"))
            retrieved = datetime.fromisoformat(evidence["retrieved_at"].replace("Z", "+00:00"))
            observed = date.fromisoformat(evidence["observation_date"])
            if published.tzinfo is None or retrieved.tzinfo is None:
                return False
            if observed > asof or published > retrieved or retrieved > decision_at or published > decision_at:
                return False
            if not evidence.get("source") or not evidence.get("vintage_id"):
                return False
            if evidence.get("license_status") not in ("AUTHORIZED", "INTERNAL_USE_AUTHORIZED"):
                return False
            if not re.fullmatch(r"[0-9a-fA-F]{64}", evidence.get("raw_sha256", "")):
                return False
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
    return True

def evaluate_crisis_backtest(rows, event_windows, signal_threshold=60, lead_days=20):
    if not event_windows:
        return {"status": "NOT_RUN", "reason": "EVENT_WINDOWS_REQUIRED",
                "metrics": None, "lookahead_protection": "Requires predeclared event windows."}
    ordered = sorted(rows, key=lambda x: x["date"])
    if len({r["date"] for r in ordered}) != len(ordered):
        raise ValueError("Duplicate as-of dates")
    for row in ordered:
        date.fromisoformat(row["date"])
    unverified = [r["date"] for r in ordered if not _has_pit_evidence(r)]
    incomplete = [r["date"] for r in ordered if r.get("score") is None or r.get("coverage_pct", 0) < 85]
    if unverified or incomplete:
        return {"status": "BLOCKED", "reason": "POINT_IN_TIME_EVIDENCE_OR_SCORE_COVERAGE_GAP",
                "unverified_dates": unverified[:20], "incomplete_score_dates": incomplete[:20],
                "metrics": None}
    windows = []
    for item in event_windows:
        start, end = item["start"], item["end"]
        date.fromisoformat(start); date.fromisoformat(end)
        if end < start:
            raise ValueError("Event end precedes start")
        windows.append(item)
    triggered = [r for r in ordered if r["score"] >= signal_threshold]
    hits, lead_times = [], []
    for event in windows:
        start, end = event["start"], event["end"]
        pre_start_index = max(0, next((i for i, r in enumerate(ordered) if r["date"] >= start), len(ordered)) - lead_days)
        pre_start = ordered[pre_start_index]["date"] if ordered else start
        candidates = [r for r in triggered if pre_start <= r["date"] <= end]
        hits.append(bool(candidates))
        if candidates:
            lead_times.append((date.fromisoformat(start) - date.fromisoformat(candidates[0]["date"])).days)
    event_dates = {d for e in windows for d in (e["start"], e["end"])}
    false_triggers = [r["date"] for r in triggered if not any(e["start"] <= r["date"] <= e["end"] for e in windows)]
    return {
        "status": "DESCRIPTIVE_ONLY", "event_count": len(windows),
        "event_detection_rate": sum(hits) / len(hits) if hits else None,
        "detected_events": sum(hits), "missed_events": len(hits) - sum(hits),
        "mean_lead_days": sum(lead_times) / len(lead_times) if lead_times else None,
        "false_trigger_days": len(false_triggers), "false_trigger_dates": false_triggers,
        "signal_threshold": signal_threshold, "lead_days": lead_days,
        "event_windows": windows,
        "warning": "Descriptive historical association only; it does not validate predictive power or optimize thresholds.",
    }
