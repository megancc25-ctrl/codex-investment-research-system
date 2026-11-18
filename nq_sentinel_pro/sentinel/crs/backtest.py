"""Point-in-time crisis backtest metrics. This refuses unsupported label or vintage claims."""
from __future__ import annotations
from datetime import date

def evaluate_crisis_backtest(rows, event_windows, signal_threshold=60, lead_days=20):
    if not event_windows:
        return {"status": "NOT_RUN", "reason": "EVENT_WINDOWS_REQUIRED",
                "metrics": None, "lookahead_protection": "Requires predeclared event windows."}
    ordered = sorted(rows, key=lambda x: x["date"])
    if len({r["date"] for r in ordered}) != len(ordered):
        raise ValueError("Duplicate as-of dates")
    for row in ordered:
        date.fromisoformat(row["date"])
    unverified = [r["date"] for r in ordered if not r.get("pit_verified", False)]
    incomplete = [r["date"] for r in ordered if r.get("score") is None or r.get("coverage_pct", 0) < 85]
    if unverified or incomplete:
        return {"status": "BLOCKED", "reason": "POINT_IN_TIME_OR_SCORE_COVERAGE_GAP",
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
