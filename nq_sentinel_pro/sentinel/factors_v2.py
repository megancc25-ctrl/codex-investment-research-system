"""Deterministic six-module research factors, without adding weights or indicators.

All factor values are supplied by audited point-in-time records. A module
requires *every* configured factor, never silently zero-fills missing ones.
Scores are candidate research transforms, not calibrated loss probabilities.
"""
import math
from .risk_v2 import WEIGHTS, observation
from .point_in_time import validate_record

# Same six modules and previously specified factor families. A factor is
# normalized to 0..100 upstream from an expanding historical window.
FACTORS = {
    "semiconductor_fundamentals": ("semiconductor_earnings", "cloud_capex_fcf", "industry_demand"),
    "trend_breadth": ("ndx_sox_trend", "sox_relative_strength", "constituent_breadth"),
    "credit_financing": ("hy_ig_ccc_spreads", "finra_margin"),
    "liquidity_leverage": ("real_yields", "fed_liquidity", "margin_leverage"),
    "valuation_earnings": ("valuation_percentile", "earnings_growth"),
    "sentiment_options": ("vix_level", "vix_term_structure"),
}

def expanding_percentile(history, current, minimum=60):
    """Past-only empirical rank. history excludes current observation."""
    clean = [float(x) for x in history if isinstance(x, (float,int))
             and not isinstance(x,bool) and math.isfinite(x)]
    if len(clean) < minimum or not math.isfinite(current):
        return None
    return 100.0 * sum(x <= current for x in clean) / len(clean)

def calculate_modules(records, decision_at, min_history=60):
    """Input records keyed by factor name, each with PIT fields and
    normalized risk percentile. No module gets VERIFIED from partial inputs.
    Returns (verified modules, comprehensive module diagnostics).
    """
    modules, diagnostics = {}, {}
    for name, factor_names in FACTORS.items():
        accepted, problems = [], {}
        for factor in factor_names:
            item = records.get(factor)
            if item is None:
                problems[factor] = "MISSING"
                continue
            eligibility = validate_record(item, decision_at)
            if not eligibility["usable"]:
                problems[factor] = eligibility["reason"]
                continue
            risk = item.get("risk_percentile")
            if isinstance(risk,bool) or not isinstance(risk,(int,float)) or not math.isfinite(risk) or not 0 <= risk <= 100:
                problems[factor] = "INVALID_RISK_PERCENTILE"
                continue
            if item.get("history_count",0) < min_history:
                problems[factor] = "INSUFFICIENT_PAST_HISTORY"
                continue
            accepted.append(item)
        diagnostics[name] = {"required":len(factor_names), "accepted":len(accepted),
                             "coverage":round(len(accepted)/len(factor_names),4),
                             "missing_or_rejected":problems}
        if problems:
            continue
        value = sum(x["risk_percentile"] for x in accepted)/len(accepted)
        modules[name] = observation(value, min(x["observation_date"] for x in accepted),
                                    "; ".join(sorted({x["source_url"] for x in accepted})),
                                    evidence=[x["indicator"] for x in accepted])
    return modules, diagnostics
