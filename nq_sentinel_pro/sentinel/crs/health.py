"""Rolling diagnostics for configured public-data sources (no market series stored)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

WINDOW_RUNS = 30


def _is_timeout(item):
    reason = str(item.get("reason") or "").lower()
    return "timeout" in reason or "timed out" in reason


def summarize_source_health(snapshots, asof, current_status, window=WINDOW_RUNS):
    runs = list(snapshots or [])[-max(0, window - 1):] + [{"asof": asof, "source_status": current_status}]
    by_source = {}
    for run in runs:
        run_day, statuses = run.get("asof"), run.get("source_status", {})
        for source, item in statuses.items():
            if source.startswith("monitoring:") or not isinstance(item, dict):
                continue
            by_source.setdefault(source, []).append((run_day, item))
    result = {}
    for source, entries in by_source.items():
        total = len(entries)
        live_ok = sum(item.get("status") == "AVAILABLE" for _, item in entries)
        cached = sum(item.get("status") == "AVAILABLE_CACHED" or item.get("cache_used") is True
                     for _, item in entries)
        timeouts = sum(_is_timeout(item) for _, item in entries)
        failures = sum(item.get("status") in ("MISSING", "INSUFFICIENT_DATA") or
                       item.get("fetch_status") == "FAILED" for _, item in entries)
        successful = [(day, item) for day, item in entries
                      if item.get("status") in ("AVAILABLE", "AVAILABLE_CACHED")]
        published_missing = sum(not item.get("published_at") for _, item in successful)
        latest_day, latest = entries[-1]
        lag = None
        observation = latest.get("observation_date")
        if observation:
            try:
                lag = (date.fromisoformat(asof) - date.fromisoformat(str(observation)[:10])).days
            except ValueError:
                lag = None
        consecutive_failures = 0
        for _, item in reversed(entries):
            if item.get("status") in ("MISSING", "INSUFFICIENT_DATA") or item.get("fetch_status") == "FAILED":
                consecutive_failures += 1
            else:
                break
        result[source] = {
            "window_runs": total, "live_successes": live_ok, "cache_uses": cached,
            "failures": failures, "timeouts": timeouts,
            "live_success_rate_pct": round(100 * live_ok / total, 1) if total else None,
            "timeout_rate_pct": round(100 * timeouts / total, 1) if total else None,
            "consecutive_failures": consecutive_failures,
            "latest_observation_date": observation, "observation_lag_days": lag,
            "published_at_missing_rate_pct": (round(100 * published_missing / len(successful), 1)
                                                if successful else None),
            "latest_quality": latest.get("quality", "UNKNOWN"),
            "latest_license_status": latest.get("license_status", "UNKNOWN"),
            "latest_reason": latest.get("reason"),
        }
    return {"window_runs_max": window, "asof": asof, "sources": result,
            "data_policy": "Source status only; no raw observations or private portfolio data."}


def load_health_snapshots(path, limit=WINDOW_RUNS - 1):
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        runs = payload if isinstance(payload, list) else []
        return runs[-limit:]
    except (OSError, ValueError):
        return []


def save_health_snapshot(path, asof, source_status, limit=WINDOW_RUNS):
    target = Path(path)
    runs = load_health_snapshots(target, limit=max(0, limit - 1))
    if not runs or runs[-1].get("asof") != asof:
        runs.append({"asof": asof, "source_status": source_status})
    else:
        runs[-1] = {"asof": asof, "source_status": source_status}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(runs[-limit:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
