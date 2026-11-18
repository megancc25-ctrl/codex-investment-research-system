"""Collect public market series independently; missing sources stay missing."""
from __future__ import annotations
from datetime import date
from .fred import SERIES, fetch_series
from .prices import TICKERS, fetch_prices
from .metrics import build_features

def collect(asof, fred_fetcher=fetch_series, price_fetcher=fetch_prices):
    date.fromisoformat(asof)
    fred, source_status = {}, {}
    for key in SERIES:
        try:
            item = fred_fetcher(key, asof)
            fred[key] = item
            source_status[f"fred:{key}"] = {"status": "AVAILABLE", "observation_date": item["observation_date"],
                                            "source": item["source"], "quality": item["quality"],
                                            "raw_sha256": item["raw_sha256"]}
        except Exception as exc:
            source_status[f"fred:{key}"] = {"status": "MISSING", "reason": str(exc)[:240]}
    price_values, price_status = price_fetcher(asof)
    source_status.update({f"market:{k}": v for k, v in price_status.items()})
    features, histories = build_features(price_values, fred, asof)
    return {"asof": asof, "fred": fred, "prices": price_values,
            "features": features, "histories": histories, "source_status": source_status,
            "expected_market_proxies": list(TICKERS)}
