"""Collect public market series independently; missing sources stay missing."""
from __future__ import annotations
from datetime import date, datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from .fred import SERIES, fetch_series
from .prices import TICKERS, fetch_prices
from .metrics import build_features

def _temporal_ages(asof, observation_date=None, retrieved_at=None, published_at=None):
    """Keep observation freshness, retrieval freshness, and release lag distinct."""
    asof_day = date.fromisoformat(asof)
    result = {"observation_age_days": None, "retrieval_age_days": None,
              "publication_lag_days": None}
    try:
        if observation_date:
            obs_day = date.fromisoformat(str(observation_date)[:10])
            result["observation_age_days"] = (asof_day - obs_day).days
    except ValueError:
        pass
    try:
        if retrieved_at:
            retrieval_day = date.fromisoformat(str(retrieved_at)[:10])
            result["retrieval_age_days"] = (asof_day - retrieval_day).days
    except ValueError:
        pass
    try:
        if observation_date and published_at:
            obs_day = date.fromisoformat(str(observation_date)[:10])
            published_day = date.fromisoformat(str(published_at)[:10])
            result["publication_lag_days"] = (published_day - obs_day).days
    except ValueError:
        pass
    return result

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

def collect(asof, fred_fetcher=fetch_series, price_fetcher=fetch_prices, fred_cache=None):
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
            source_status[f"fred:{key}"] = {"status": "AVAILABLE", "fetch_status": "SUCCESS", "observation_date": item["observation_date"],
                                            "source": item["source"], "source_id": item["series_id"],
                                            "published_at": item.get("published_at"),
                                            "retrieved_at": item.get("retrieved_at"),
                                            **_temporal_ages(asof, item.get("observation_date"), item.get("retrieved_at"), item.get("published_at")),
                                            "quality": item["quality"],
                                            "license_status": item.get("license_status", "REVIEW_REQUIRED"),
                                            "cache_authorization": item.get("cache_authorization", "NOT_APPROVED"),
                                            "raw_sha256": item["raw_sha256"]}
        except Exception as exc:
            cache_item = (fred_cache or {}).get(key)
            if cache_item:
                cached = dict(cache_item)
                fred[key] = cached
                source_status[f"fred:{key}"] = {"status": "AVAILABLE_CACHED", "fetch_status": "FAILED",
                                             "source_id": cached.get("series_id", SERIES[key]),
                                             "source": cached.get("source"),
                                             "observation_date": cached.get("observation_date"),
                                             "published_at": cached.get("published_at"),
                                             "retrieved_at": cached.get("retrieved_at"),
                                             **_temporal_ages(asof, cached.get("observation_date"), cached.get("retrieved_at"), cached.get("published_at")),
                                             "quality": cached.get("quality", "UNKNOWN"),
                                             "license_status": cached.get("license_status", "UNKNOWN"),
                                             "cache_authorization": cached.get("cache_authorization", "UNKNOWN"),
                                             "raw_sha256": cached.get("raw_sha256"),
                                             "cache_used": True, "cache_age_days": cached.get("cache_age_days"),
                                             "observation_age_days": cached.get("observation_age_days"),
                                             "retrieval_age_days": cached.get("cache_retrieval_age_days"),
                                             "cache_retrieval_age_days": cached.get("cache_retrieval_age_days"),
                                             "cache_max_age_days": cached.get("cache_max_age_days"),
                                             "reason": str(exc)[:240]}
                continue
            source_status[f"fred:{key}"] = {"status": "MISSING", "fetch_status": "FAILED", "source_id": SERIES[key],
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
            **_temporal_ages(asof, item.get("latest_date"), item.get("retrieved_at"), None),
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
            "price_status": price_status,
            "price_status": price_status,
            "features": features, "histories": histories, "source_status": source_status,
            "expected_market_proxies": list(TICKERS)}
