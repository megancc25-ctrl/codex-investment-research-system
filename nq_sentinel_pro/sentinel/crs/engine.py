"""Deterministic cross-asset scoring with explicit coverage and no missing-value zero fill."""
from __future__ import annotations
import math
from .config import (CRITICAL_METRICS, CRITICAL_MODULES, GROUPS, MIN_PERCENTILE_HISTORY, MIN_TOTAL_COVERAGE,
                     MODULE_WEIGHTS, PERCENTILE_WINDOW, PERCENTILE_WEIGHT,
                     RULES, THRESHOLD_WEIGHT)

def threshold_score(metric, value):
    if metric not in RULES or value is None:
        return None
    if isinstance(value, bool):
        if metric not in ("ndx_below_200dma", "synchronized_three_asset_down_20d", "synchronized_three_asset_loss_5pct"):
            return None
        value = int(value)
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    _module, _group, polarity, levels = RULES[metric]
    score = 0.0
    for boundary, points in levels:
        if (polarity == "high" and value >= boundary) or (polarity == "low" and value <= boundary):
            score = float(points)
    return score

def percentile_risk(history, current, polarity):
    """Empirical risk rank using prior observations only; None below the history floor."""
    clean = [float(x) for x in history if isinstance(x, (int, float))
             and not isinstance(x, bool) and math.isfinite(float(x))]
    if len(clean) < MIN_PERCENTILE_HISTORY or not isinstance(current, (int, float)) or not math.isfinite(float(current)):
        return None
    rank = 100.0 * sum(x <= current for x in clean) / len(clean)
    return rank if polarity == "high" else 100.0 - rank

def coverage_sufficient(coverage_pct):
    """Gate on unrounded coverage; display rounding must not change publication eligibility."""
    return isinstance(coverage_pct, (int, float)) and math.isfinite(float(coverage_pct)) and coverage_pct >= MIN_TOTAL_COVERAGE

def _assess_metric(name, record, histories):
    if isinstance(record, dict):
        value, quality = record.get("value"), record.get("quality", "UNKNOWN")
        stale, source, age_days = bool(record.get("stale", False)), record.get("source"), record.get("age_days")
        published_at, retrieved_at = record.get("published_at"), record.get("retrieved_at")
        license_status = record.get("license_status", "REVIEW_REQUIRED")
    else:
        value, quality, stale, source, age_days = record, "UNVERIFIED_VENDOR_PROXY", False, None, None
        published_at = retrieved_at = None
        license_status = "REVIEW_REQUIRED"
    base = threshold_score(name, value)
    if base is None or stale:
        return None
    _module, _group, polarity, _levels = RULES[name]
    pct = percentile_risk(histories.get(name, [])[-PERCENTILE_WINDOW:], value, polarity)
    score = THRESHOLD_WEIGHT * base + PERCENTILE_WEIGHT * pct if pct is not None else base
    return {"value": value, "threshold_score": base, "percentile_score": pct,
            "score": round(max(0.0, min(100.0, score)), 2),
            "method": "threshold_plus_past_percentile" if pct is not None else "threshold_only_provisional",
            "quality": quality, "source": source, "age_days": age_days,
            "published_at": published_at, "retrieved_at": retrieved_at,
            "license_status": license_status}

def score_snapshot(features, histories=None):
    histories = histories or {}
    grouped = {module: {} for module in MODULE_WEIGHTS}
    details, qualities, missing = {}, [], []
    for name, (module, group, _polarity, _levels) in RULES.items():
        assessment = _assess_metric(name, features.get(name), histories)
        if assessment is None:
            missing.append(name)
            details[name] = {"status": "MISSING_OR_STALE", "value": None, "group": group, "module": module}
            continue
        details[name] = {"status": "AVAILABLE", "group": group, "module": module, **assessment}
        grouped[module].setdefault(group, []).append(assessment)
        qualities.append(assessment["quality"])

    modules, weighted_coverage, available_weight = {}, 0.0, 0
    for module, weight in MODULE_WEIGHTS.items():
        expected, present = GROUPS[module], grouped[module]
        coverage = len(present) / len(expected) if expected else 0.0
        weighted_coverage += weight * coverage
        group_scores = {g: max(item["score"] for item in records) for g, records in present.items()}
        score = round(sum(group_scores.values()) / len(group_scores), 2) if group_scores else None
        if score is not None:
            available_weight += weight
        modules[module] = {
            "weight_pct": weight, "score": score, "coverage_pct": round(100 * coverage, 1),
            "groups_available": sorted(present), "groups_expected": expected,
            "group_scores": group_scores,
            "status": "AVAILABLE" if coverage == 1 else "PARTIAL" if present else "MISSING",
        }

    coverage_raw = weighted_coverage
    coverage = round(coverage_raw, 1)
    critical_missing = [m for m in CRITICAL_MODULES if modules[m]["score"] is None]
    critical_metrics_missing = [name for name in CRITICAL_METRICS
                                if details.get(name, {}).get("status") != "AVAILABLE"]
    if available_weight:
        contributions = {m: MODULE_WEIGHTS[m] * modules[m]["score"] / 100
                         for m in MODULE_WEIGHTS if modules[m]["score"] is not None}
        partial_sum = round(sum(contributions.values()), 2)
        normalized = round(100 * partial_sum / available_weight, 2)
    else:
        partial_sum = normalized = None
    publishable = (coverage_sufficient(coverage_raw) and not critical_missing
                   and not critical_metrics_missing and normalized is not None)
    score = normalized if publishable else None

    if not qualities:
        confidence = "NONE"
    elif any(q in ("UNVERIFIED_VENDOR_PROXY", "LICENSE_RESTRICTED", "UNKNOWN") for q in qualities):
        confidence = "LOW"
    elif any(q in ("CURRENT_VINTAGE", "PUBLICATION_TIME_UNKNOWN", "STALE_MONTHLY") for q in qualities):
        confidence = "MEDIUM"
    else:
        confidence = "MEDIUM"

    return {
        "score": score, "status": "RESEARCH_ONLY_UNVALIDATED" if publishable else "INSUFFICIENT_DATA",
        "data_coverage_pct": coverage, "data_coverage_unrounded_pct": coverage_raw,
        "data_confidence": confidence,
        "critical_modules_missing": critical_missing,
        "critical_metrics_missing": critical_metrics_missing, "missing_metrics": missing,
        "modules": modules, "metric_details": details,
        "partial_contribution_sum_not_score": partial_sum,
        "renormalized_diagnostic_not_validated": normalized, "score_is_probability": False,
        "notes": [
            "Research descriptor only; score is not a crisis probability.",
            "0.6 threshold / 0.4 percentile weighting and all cutoffs remain provisional.",
            "Threshold-only scores are provisional when prior history is below 252 observations.",
            "Within-group signals are capped at the maximum to limit duplicate counting.",
        ],
    }
