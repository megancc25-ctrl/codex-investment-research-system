"""V2 research risk scoring. Missing observations never become zero risk.

Scores are UNVALIDATED research descriptors, not probabilities or portfolio weights.
Each module observation must be independently sourced and timestamped.
"""
from datetime import date

VERSION = "2.0.0-research"
WEIGHTS = {
    "semiconductor_fundamentals": 25,
    "trend_breadth": 25,
    "credit_financing": 20,
    "liquidity_leverage": 15,
    "valuation_earnings": 10,
    "sentiment_options": 5,
}
MIN_COVERAGE = 0.80
REQUIRED = ("trend_breadth", "credit_financing", "semiconductor_fundamentals")

def observation(score, asof, source, quality="VERIFIED", evidence=None):
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
        raise ValueError("Module risk score must be numeric 0..100")
    date.fromisoformat(asof)
    if not source or quality not in ("VERIFIED", "UNVERIFIED_VENDOR_PROXY"):
        raise ValueError("Source and valid quality required")
    return {"score": float(score), "asof": asof, "source": source,
            "quality": quality, "evidence": evidence or []}

def technical_observations(signal, asof):
    """Explicitly provisional; 200dma/relative momentum/volatility only.
    Breadth is seven selected stocks, NOT SOX/NDX constituent breadth.
    Volatility is realized NDX volatility, NOT VIX or its term structure.
    """
    trend = (30 * (signal["ndx_vs_200dma"] < 0)
             + 30 * (signal["sox_vs_200dma"] < 0)
             + 25 * (signal["sox_relative_ndx_20d"] < -0.05))
    breadth = signal.get("breadth_50dma")
    if breadth is not None:
        trend += 15 * (breadth < 0.40)
        trend /= 1.0
    else:
        trend = trend / 85 * 100
    vol = signal["ndx_20d_realized_vol"]
    return {
        "trend_breadth": observation(min(100, trend), asof, "Yahoo/yfinance close proxy",
                                      "UNVERIFIED_VENDOR_PROXY",
                                      ["NDX/SOX 200dma, SOX/NDX 20d, seven-stock breadth (if available)"]),
        "sentiment_options": observation(100 if vol > .40 else 65 if vol > .30 else 30 if vol > .20 else 10,
                                          asof, "Yahoo/yfinance realized NDX volatility",
                                          "UNVERIFIED_VENDOR_PROXY",
                                          ["Realized volatility proxy; VIX term structure MISSING"])
    }

def score_v2(modules, previous=None):
    """Full score only with >=80% verified weight and mandatory independent modules.
    No rescaling missing module weight into an apparently complete 0-100 score.
    """
    unknown = set(modules) - set(WEIGHTS)
    if unknown:
        raise ValueError("Unknown modules: " + repr(sorted(unknown)))
    covered = 0
    verified = 0
    contributions = {}
    details = {}
    for name, weight in WEIGHTS.items():
        item = modules.get(name)
        if item is None:
            details[name] = {"weight": weight, "status": "MISSING", "contribution": None}
            continue
        item = observation(item["score"], item["asof"], item["source"],
                           item.get("quality", "VERIFIED"), item.get("evidence", []))
        covered += weight
        if item["quality"] == "VERIFIED":
            verified += weight
        contribution = round(weight * item["score"] / 100, 4)
        contributions[name] = contribution
        details[name] = {"weight": weight, "status": item["quality"],
                         "score": item["score"], "contribution": contribution,
                         "asof": item["asof"], "source": item["source"],
                         "evidence": item["evidence"]}
    mandatory_ok = all(details[k]["status"] == "VERIFIED" for k in REQUIRED)
    publishable = verified >= MIN_COVERAGE * 100 and mandatory_ok
    total = round(sum(contributions.values()), 2) if publishable else None
    comparable = bool(publishable and previous
                      and previous.get("version") == VERSION
                      and previous.get("score") is not None
                      and previous.get("status") == "RESEARCH_UNVALIDATED")
    return {"version": VERSION, "score": total,
            "status": "RESEARCH_UNVALIDATED" if publishable else "INSUFFICIENT_VERIFIED_DATA",
            "coverage_pct": covered, "verified_coverage_pct": verified,
            "required_verified": mandatory_ok,
            "module_details": details,
            "partial_contribution_sum_NOT_SCORE": round(sum(contributions.values()), 2),
            "previous_score": previous["score"] if comparable else None,
            "delta": round(total - previous["score"], 2) if comparable else None,
            "comparable": comparable,
            "note": "Weights and cutoffs UNVALIDATED; not a calibrated loss probability or trade signal."}
