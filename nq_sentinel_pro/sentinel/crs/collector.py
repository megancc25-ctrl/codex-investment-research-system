"""Collect public market series independently; missing sources stay missing."""
from __future__ import annotations
from datetime import date, datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from .fred import SERIES, fetch_series
from .prices import TICKERS, fetch_prices
from .metrics import build_features

MONITORING_GAPS = {
    "breadth": ("MISSING", "No constituent breadth source is connected."),
    "move": ("MISSING", "No MOVE data source is connected."),
    "repo_rate_volume": ("MISSING", "No continuous repo rate or volume history is connected; a manual event flag is not a series."),
    "cdx_ig_hy": ("MISSING", "No CDX IG/HY point or history feed is connected; manual HY widening is only a boolean event."),
    "dxy_direct": ("PROXY_ONLY", "FRED broad trade-weighted USD is not ICE DXY; Yahoo DX-Y.NYB is an unreconciled proxy."),
    "ust_total_return": ("PROXY_ONLY", "IEF is an ETF proxy, not a broad US Treasury total-return index."),
    "gold_spot": ("PROXY_ONLY", "GLD is an ETF proxy, not a spot gold benchmark."),
    "global_real_estate": ("US_ONLY", "Connected housing data cover US Case-Shiller and existing home sales only."),
    "oas_pit_history": ("RESTRICTED_HISTORY", "HY/IG OAS use current-vintage FRED observations and restricted ICE data; no release-vintage history is available in this adapter."),
}

def collect(asof, fred_fetcher=fetch_series, price_fetcher=fetch_prices):
    date.fromisoformat(asof)
    fred, source_status = {}, {}
    with ThreadPoolExecutor(max_workers=min(8, len(SERIES))) as pool:
        futures = {pool.submit(fred_fetcher, key, asof): key for key in SERIES}
        results = {}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = (future.result(), None)
            except Exception as exc:
                results[key] = (None, exc)
    for key in SERIES:
        try:
            item, error = results[key]
            if error:
                raise error
            fred[key] = item
            source_status[f"fred:{key}"] = {"status": "AVAILABLE", "observation_date": item["observation_date"],
                                            "source": item["source"], "source_id": item["series_id"],
                                            "published_at": item.get("published_at"),
                                            "retrieved_at": item.get("retrieved_at"),
                                            "quality": item["quality"],
                                            "license_status": item.get("license_status", "REVIEW_REQUIRED"),
                                            "raw_sha256": item["raw_sha256"]}
        except Exception as exc:
            source_status[f"fred:{key}"] = {"status": "MISSING", "source_id": SERIES[key],
                                             "source": f"FRED series {SERIES[key]}",
                                             "observation_date": None, "published_at": None,
                                             "retrieved_at": datetime.now(timezone.utc).isoformat(), "quality": "MISSING",
                                             "license_status": "REVIEW_REQUIRED",
                                             "reason": str(exc)[:240]}
    price_values, price_status = price_fetcher(asof)
    for key in TICKERS:
        item = price_status.get(key, {})
        source_status[f"market:{key}"] = {
            **item, "status": item.get("status", "MISSING"),
            "observation_date": item.get("latest_date"), "published_at": None,
            "license_status": "REVIEW_REQUIRED",
        }
    for key, (status, reason) in MONITORING_GAPS.items():
        source_status[f"monitoring:{key}"] = {
            "status": status, "source": None, "source_id": None,
            "observation_date": None, "published_at": None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "quality": status, "license_status": "REVIEW_REQUIRED", "reason": reason,
        }
    features, histories = build_features(price_values, fred, asof, price_status=price_status)
    return {"asof": asof, "fred": fred, "prices": price_values,
            "features": features, "histories": histories, "source_status": source_status,
            "expected_market_proxies": list(TICKERS)}
