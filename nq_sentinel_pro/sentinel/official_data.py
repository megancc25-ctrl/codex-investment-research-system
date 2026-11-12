"""Public official-source adapters. No credentials, positions or broker data.

FRED observations are historical and publication-lagged, not live market prices.
Unavailable/stale/conflicting data fail closed and remain MISSING.
"""
import csv
import io
import json
import math
import urllib.request
from datetime import date, timedelta
from pathlib import Path

FRED = {
    "hy_oas": ("BAMLH0A0HYM2", 7),
    "ig_oas": ("BAMLC0A0CM", 7),
    "ccc_oas": ("BAMLH0A3HYC", 7),
    "treasury_10y": ("DGS10", 7),
    "tips_10y": ("DFII10", 7),
    "vix": ("VIXCLS", 7),
    "initial_claims": ("ICSA", 21),
    "fed_balance_sheet": ("WALCL", 21),
    "gdp": ("GDP", 150),
}
SOURCE_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="

def fred_csv(series, asof, opener=None):
    """Download official FRED CSV, never future-date observations."""
    if series not in (v[0] for v in FRED.values()):
        raise ValueError("Series not allowlisted")
    date.fromisoformat(asof)
    url = SOURCE_BASE + series
    opener = opener or (lambda u: urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "NQ-Sentinel-Research/2.0"}), timeout=15))
    with opener(url) as response:
        raw = response.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or len(reader.fieldnames) != 2 or series not in reader.fieldnames:
        raise ValueError("Unexpected FRED CSV schema")
    values = []
    for row in reader:
        day = row[reader.fieldnames[0]]
        if day > asof or row[series] in ("", "."):
            continue
        v = float(row[series])
        if math.isfinite(v):
            values.append((day, v))
    if not values:
        raise ValueError("No historical FRED observation")
    day, value = max(values)
    return {"value": value, "asof": day, "source": url,
            "quality": "VERIFIED", "series": series}

def fetch_official(asof, opener=None):
    """Per-series error isolation; no fabricated fallback."""
    observations, errors = {}, {}
    for name, (series, max_lag) in FRED.items():
        try:
            item = fred_csv(series, asof, opener)
            age = (date.fromisoformat(asof) - date.fromisoformat(item["asof"])).days
            if age > max_lag:
                raise ValueError(f"STALE {age} days (limit {max_lag})")
            observations[name] = item
        except Exception as exc:
            errors[name] = "MISSING: " + str(exc)[:200]
    return {"asof": asof, "observations": observations, "errors": errors,
            "note": "FRED published observation date is not necessarily release timestamp."}

def load_manual_evidence(path, asof):
    """Only vetted allowlisted public sources; manually curated inputs are
    explicitly unverified until independently reviewed, never silently promoted.
    No personal positions or private data allowed.
    """
    if not path:
        return {}
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or set(obj) - {
        "semiconductor_fundamentals", "valuation_earnings", "liquidity_leverage",
        "credit_financing", "trend_breadth", "sentiment_options"
    }:
        raise ValueError("Unexpected evidence keys")
    result = {}
    for key, item in obj.items():
        if not isinstance(item, dict) or not all(k in item for k in ("score", "asof", "source")):
            raise ValueError("Evidence requires score, asof, source")
        if date.fromisoformat(item["asof"]) > date.fromisoformat(asof):
            raise ValueError("Future-dated evidence")
        source = item["source"]
        if not isinstance(source, str) or not source.startswith("https://"):
            raise ValueError("Evidence must contain HTTPS source")
        result[key] = dict(item, quality="UNVERIFIED_VENDOR_PROXY",
                           evidence=(item.get("evidence") or []) + ["Manual evidence pending independent verification"])
    return result

def official_module_observations(snapshot):
    """Research-only candidate rules, not statistically calibrated thresholds.
    FRED OAS are spreads in percentage points; never CDX HY prices in bp.
    Modules are VERIFIED only if the necessary independent official fields exist.
    """
    from .risk_v2 import observation
    d = snapshot["observations"]
    result = {}
    if all(x in d for x in ("hy_oas", "ig_oas", "ccc_oas")):
        hy, ig, ccc = (d[x]["value"] for x in ("hy_oas", "ig_oas", "ccc_oas"))
        # Conservative fixed candidate thresholds; never infer precise crash probability.
        score = min(100, 35 * (hy >= 4) + 30 * (hy >= 6)
                    + 20 * (ccc >= 10) + 15 * (ig >= 1.5))
        result["credit_financing"] = observation(
            score, min(d[x]["asof"] for x in ("hy_oas", "ig_oas", "ccc_oas")),
            "; ".join(d[x]["source"] for x in ("hy_oas", "ig_oas", "ccc_oas")),
            evidence=[f"FRED HY OAS={hy:.3f} percentage points",
                      f"IG OAS={ig:.3f} percentage points; CCC OAS={ccc:.3f}",
                      "Thresholds UNVALIDATED; CDX and tech excess OAS MISSING"])
    if "vix" in d:
        v = d["vix"]["value"]
        score = 100 if v >= 40 else 75 if v >= 30 else 50 if v >= 25 else 25 if v >= 20 else 10
        # VIX alone is not the full sentiment/options module; retain unverified status.
        result["sentiment_options"] = observation(
            score, d["vix"]["asof"], d["vix"]["source"],
            quality="UNVERIFIED_VENDOR_PROXY",
            evidence=[f"VIX={v}; term structure and VRP MISSING"])
    # Treasury rates, claims and balance sheet are reported as inputs only.
    # A single yield level or Fed assets snapshot cannot verify liquidity/leverage.
    return result
