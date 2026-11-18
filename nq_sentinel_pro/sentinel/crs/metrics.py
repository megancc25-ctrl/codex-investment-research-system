"""Cross-asset feature calculations from explicit as-of time series."""
from __future__ import annotations
from datetime import date
import hashlib
import json

def _clean(series, asof):
    return [(d, float(v)) for d, v in sorted(series.items()) if d <= asof and v is not None]

def _return_series(series, lag=20):
    return [(series[i][0], series[i][1] / series[i-lag][1] - 1.0)
            for i in range(lag, len(series)) if series[i-lag][1] > 0 and series[i][1] > 0]

def _change_series(series, lag=20, multiplier=100.0):
    return [(series[i][0], (series[i][1] - series[i-lag][1]) * multiplier)
            for i in range(lag, len(series))]

def _drawdown_series(series, window=63):
    rows = []
    for i in range(window - 1, len(series)):
        peak = max(v for _, v in series[i-window+1:i+1])
        rows.append((series[i][0], max(0.0, peak / series[i][1] - 1.0)))
    return rows

def _current(rows):
    return rows[-1] if rows else None

def _correlation(left, right, window):
    left_map, right_map = dict(left), dict(right)
    days = sorted(set(left_map) & set(right_map))[-window:]
    if len(days) < window:
        return []
    xs, ys = [left_map[d] for d in days], [right_map[d] for d in days]
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    vx = sum((x-mx)**2 for x in xs)
    vy = sum((y-my)**2 for y in ys)
    if vx == 0 or vy == 0:
        return []
    corr = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / (vx*vy)**0.5
    return [(days[-1], max(-1.0, min(1.0, corr)), days[0], days[-1], len(days))]

def _common_asset_returns(series_by_asset, lag=20, min_common=None):
    """Return aligned lag returns, using only dates shared by every input series."""
    min_common = lag + 1 if min_common is None else min_common
    maps = [{d: value for d, value in series if value is not None and value > 0} for series in series_by_asset]
    common = sorted(set.intersection(*(set(m) for m in maps))) if maps else []
    if len(common) < min_common:
        return {}, common
    selected = common[-(lag + 1):]
    returns = {i: maps[i][selected[-1]] / maps[i][selected[0]] - 1.0 for i in range(len(maps))}
    return returns, selected

def _record(value, source, quality, obs_date, asof, stale=False, provenance=None):
    if value is None:
        return None
    age = (date.fromisoformat(asof) - date.fromisoformat(obs_date)).days
    provenance = provenance or {}
    provenance = {"source_id": "UNKNOWN", "ticker": "UNKNOWN", "raw_sha256": None,
                  "published_at": None, "retrieved_at": None, "license_status": "UNKNOWN",
                  **provenance}
    record = {"value": value, "source": provenance.get("source", source), "quality": provenance.get("quality", "STALE_MONTHLY" if stale else quality),
            "observation_date": obs_date, "published_at": provenance.get("published_at"),
            "retrieved_at": provenance.get("retrieved_at"),
            "license_status": provenance.get("license_status", "UNKNOWN"),
            "source_id": provenance.get("source_id", "UNKNOWN"),
            "ticker": provenance.get("ticker", "UNKNOWN"),
            "raw_sha256": provenance.get("raw_sha256"),
            "age_days": age, "stale": stale}
    for key in ("window_start_date", "window_end_date", "window_observation_count",
                "window_observation_dates", "component_source_ids", "component_provenance"):
        if key in provenance:
            record[key] = provenance[key]
    return record

def _latest_fred(fred, key):
    item = fred.get(key)
    if not item or not item.get("values"):
        return None
    day = max(item["values"])
    return item["values"][day], day, item

def _common_change(fred, a, b, lag=20):
    left, right = fred.get(a, {}).get("values", {}), fred.get(b, {}).get("values", {})
    common = sorted(set(left) & set(right))
    if len(common) <= lag:
        return None
    d = common[-1]
    return (left[common[-1]] - left[common[-1-lag]]) * 100, d

def build_features(prices, fred, asof, price_status=None):
    asof = str(asof)
    features, histories = {}, {}
    price_series = {k: _clean(v, asof) for k, v in prices.items()}
    fred_series = {k: _clean(v.get("values", {}), asof) for k, v in fred.items()}
    price_meta = price_status or {k: v for k, v in prices.items() if isinstance(v, dict) and "values" not in v}
    fred_meta = fred

    def price_provenance(key):
        meta = price_meta.get(key, {})
        ticker = meta.get("ticker", "UNKNOWN")
        return {**meta, "source_id": meta.get("source_id", f"yahoo:{ticker}" if ticker != "UNKNOWN" else "UNKNOWN"),
                "ticker": ticker, "raw_sha256": meta.get("raw_sha256"),
                "license_status": meta.get("license_status", "REVIEW_REQUIRED" if meta else "UNKNOWN")}

    def fred_provenance(key):
        meta = fred_meta.get(key, {})
        return {**meta, "source_id": meta.get("series_id", "UNKNOWN"), "ticker": "N/A",
                "raw_sha256": meta.get("raw_sha256"),
                "license_status": meta.get("license_status", "REVIEW_REQUIRED" if meta else "UNKNOWN")}

    def put(name, rows, source, quality, provenance=None, transform=lambda x: x, stale_after=5, window=None):
        rows = [(d, transform(v)) for d, v in rows]
        current = _current(rows)
        histories[name] = [v for d, v in rows[:-1] if d < asof]
        if current is None:
            return
        day, value = current
        meta = dict(provenance or {})
        if window:
            meta["window_start_date"], meta["window_end_date"] = window
            meta["window_observation_dates"] = [d for d, _ in rows if window[0] <= d <= window[1]]
        features[name] = _record(value, source, quality, day, asof,
                                 (date.fromisoformat(asof)-date.fromisoformat(day)).days > stale_after,
                                 meta)

    # Equity and cross-asset traded proxies.
    for key, metric in (("ndx", "ndx_drawdown_63d"), ("sox", "sox_drawdown_63d")):
        rows = price_series.get(key, [])
        meta = price_meta.get(key, {})
        dd = _drawdown_series(rows, 63)
        if key == "ndx":
            put(metric, dd, meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance(key))
            if len(rows) >= 200:
                d, current = rows[-1]
                avg = sum(v for _, v in rows[-200:]) / 200
                features["ndx_below_200dma"] = _record(current < avg, meta.get("source", "Yahoo Finance"),
                    meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), d, asof,
                    (date.fromisoformat(asof)-date.fromisoformat(d)).days > 5, price_provenance(key))
                gap = max(0.0, (avg-current)/avg) if avg else None
                features["ndx_gap_below_200dma"] = _record(gap, meta.get("source", "Yahoo Finance"),
                    meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), d, asof,
                    (date.fromisoformat(asof)-date.fromisoformat(d)).days > 5, price_provenance(key))
            put("ndx_return_20d", _return_series(rows, 20), meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance(key))
        else:
            put(metric, dd, meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance(key))
        if key == "ndx":
            put("stock_return_20d", _return_series(rows, 20), meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance(key))
    vix = fred.get("vix", {})
    if vix:
        put("vix_level", _clean(vix["values"], asof), vix["source"], vix["quality"], fred_provenance("vix"), stale_after=7)
    # No market-breadth feed is currently available: do not make one up.
    if price_series.get("bond_total_return_proxy"):
        meta = price_meta.get("bond_total_return_proxy", {})
        put("bond_return_20d", _return_series(price_series["bond_total_return_proxy"], 20),
            meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance("bond_total_return_proxy"))
    if price_series.get("gold_proxy"):
        meta = price_meta.get("gold_proxy", {})
        gold_rows = price_series["gold_proxy"]
        put("gold_return_20d", _return_series(gold_rows, 20), meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance("gold_proxy"))
        rolling = []
        for i in range(20, len(gold_rows)):
            high = max(v for _, v in gold_rows[i-20:i+1])
            rolling.append((gold_rows[i][0], max(0.0, high/gold_rows[i][1]-1)))
        put("gold_drawdown_20d", rolling, meta.get("source", "Yahoo Finance"), meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance("gold_proxy"))
    dollar_rows = fred_series.get("broad_usd", [])
    if dollar_rows:
        meta = fred_meta["broad_usd"]
        put("usd_20d_change_pct", _return_series(dollar_rows, 20),
            meta["source"] + " (broad trade-weighted USD, not DXY)", meta["quality"], fred_provenance("broad_usd"), stale_after=14)
    elif price_series.get("dxy_proxy"):
        meta = price_meta.get("dxy_proxy", {})
        put("usd_20d_change_pct", _return_series(price_series["dxy_proxy"], 20), meta.get("source", "Yahoo Finance"),
            meta.get("quality", "UNVERIFIED_VENDOR_PROXY"), price_provenance("dxy_proxy"))

    # Rates are percentage-point levels; changes convert percentage points to basis points.
    for series_key, feature in (("ust10y", "ust10y_change_20d_bp"), ("ust30y", "ust30y_change_20d_bp"),
                                ("real10y", "real10y_change_20d_bp")):
        rows = fred_series.get(series_key, [])
        if rows:
            meta = fred_meta[series_key]
            put(feature, _change_series(rows, 20, 100), meta["source"], meta["quality"], fred_provenance(series_key), stale_after=10)
    sofr, iorb = fred_series.get("sofr", []), fred_series.get("iorb", [])
    by_day_s, by_day_i = dict(sofr), dict(iorb)
    common = sorted(set(by_day_s) & set(by_day_i))
    if common:
        spread = [(d, (by_day_s[d] - by_day_i[d]) * 100) for d in common]
        meta = fred_meta["sofr"]
        put("sofr_iorb_gap_bp", spread, meta["source"], meta["quality"], fred_provenance("sofr"), stale_after=7)
    reserves = fred_series.get("reserves", [])
    if len(reserves) >= 5:
        put("fed_reserves_change_4w_pct", _return_series(reserves, 4),
            fred_meta["reserves"]["source"], fred_meta["reserves"]["quality"], fred_provenance("reserves"), stale_after=21)

    # HY OAS is quoted in percentage points in FRED. Convert to basis points explicitly.
    for series_key, feature in (("hy_oas", "hy_oas_bp"), ("ig_oas", "ig_oas_bp")):
        rows = fred_series.get(series_key, [])
        if rows:
            meta = fred_meta[series_key]
            put(feature, rows, meta["source"], meta["quality"], fred_provenance(series_key), lambda x: x * 100.0, stale_after=10)
    hy = fred_series.get("hy_oas", [])
    if hy:
        meta = fred_meta["hy_oas"]
        put("hy_oas_change_20d_bp", _change_series(hy, 20, 100), meta["source"], meta["quality"], fred_provenance("hy_oas"), stale_after=10)
    nfci = fred_series.get("nfci", [])
    if nfci:
        meta = fred_meta["nfci"]
        put("nfci_level", nfci, meta["source"], meta["quality"], fred_provenance("nfci"), stale_after=21)
    stlfsi = fred_series.get("stlfsi", [])
    if stlfsi:
        meta = fred_meta["stlfsi"]
        put("stlfsi_level", stlfsi, meta["source"], meta["quality"], fred_provenance("stlfsi"), stale_after=21)

    # Housing fundamentals: monthly, US-only, with a separate freshness clock.
    home, cpi = fred_series.get("case_shiller", []), fred_series.get("cpi", [])
    hp_map, cpi_map = dict(home), dict(cpi)
    common_months = sorted(set(hp_map) & set(cpi_map))
    if len(common_months) >= 13:
        current_month, prior_month = common_months[-1], common_months[-13]
        real_growth = ((hp_map[current_month] / cpi_map[current_month]) /
                       (hp_map[prior_month] / cpi_map[prior_month]) - 1) * 100
        meta = fred_meta["case_shiller"]
        features["real_home_price_yoy_pct"] = _record(real_growth, meta["source"], meta["quality"],
                                                       current_month, asof,
                                                       (date.fromisoformat(asof)-date.fromisoformat(current_month)).days > 75,
                                                       fred_provenance("case_shiller"))
        histories["real_home_price_yoy_pct"] = [
            ((hp_map[common_months[i]] / cpi_map[common_months[i]]) /
             (hp_map[common_months[i-12]] / cpi_map[common_months[i-12]]) - 1) * 100
            for i in range(12, len(common_months)-1)
        ]
    sales = fred_series.get("home_sales", [])
    if len(sales) >= 13:
        d, value = sales[-1]
        prior = sales[-13][1]
        growth = (value / prior - 1) * 100 if prior else None
        meta = fred_meta["home_sales"]
        features["home_sales_yoy_pct"] = _record(growth, meta["source"], meta["quality"], d, asof,
                                                  (date.fromisoformat(asof)-date.fromisoformat(d)).days > 75,
                                                  fred_provenance("home_sales"))
        histories["home_sales_yoy_pct"] = [
            (sales[i][1] / sales[i-12][1] - 1) * 100 for i in range(12, len(sales)-1) if sales[i-12][1]
        ]

    # Joint features use a common date set; per-series return windows are not interchangeable.
    common_returns, common_days = _common_asset_returns([
        price_series.get("ndx", []), price_series.get("bond_total_return_proxy", []),
        price_series.get("gold_proxy", []),
    ], lag=20)
    stock, bond, gold = (common_returns.get(i) for i in range(3))
    window = (common_days[0], common_days[-1]) if common_days else None
    window_provenance = {"source_id": "joint:" + ":".join(price_provenance(k).get("source_id", "UNKNOWN") for k in ("ndx", "bond_total_return_proxy", "gold_proxy")),
                         "ticker": "NDX|IEF|GLD", "raw_sha256": hashlib.sha256("|".join(str(price_provenance(k).get("raw_sha256") or "UNKNOWN") for k in ("ndx", "bond_total_return_proxy", "gold_proxy")).encode()).hexdigest(),
                         "retrieved_at": max((price_provenance(k).get("retrieved_at") or "") for k in ("ndx", "bond_total_return_proxy", "gold_proxy")) or None,
                         "license_status": "REVIEW_REQUIRED", "component_source_ids": [price_provenance(k).get("source_id", "UNKNOWN") for k in ("ndx", "bond_total_return_proxy", "gold_proxy")],
                         "component_provenance": [{key: price_provenance(k).get(key) for key in ("source_id", "ticker", "source", "observation_date", "published_at", "retrieved_at", "raw_sha256", "quality", "license_status")} for k in ("ndx", "bond_total_return_proxy", "gold_proxy")]}
    aligned_returns = []
    if len(common_days) >= 21:
        used = common_days[-21:]
        for key in ("ndx", "bond_total_return_proxy", "gold_proxy"):
            mapped = dict(price_series.get(key, []))
            aligned_returns.append([(d, mapped[d] / mapped[used[i-1]] - 1)
                                    for i, d in enumerate(used) if i > 0])
    for feature, left, right, a, b in (
        ("stock_bond_corr_20d", aligned_returns[0] if aligned_returns else [], aligned_returns[1] if aligned_returns else [], "NDX", "IEF"),
        ("stock_gold_corr_20d", aligned_returns[0] if aligned_returns else [], aligned_returns[2] if aligned_returns else [], "NDX", "GLD"),
    ):
        corr_rows = _correlation(left, right, 20)
        if corr_rows:
            _obs_day, corr_value, start_day, end_day, obs_count = corr_rows[-1]
            other_key = "bond_total_return_proxy" if b == "IEF" else "gold_proxy"
            prov_a, prov_b = price_provenance("ndx"), price_provenance(other_key)
            corr_provenance = {**window_provenance, "ticker": f"{a}|{b}",
                                            "source_id": f"joint:{price_provenance('ndx').get('source_id')}:{price_provenance('bond_total_return_proxy' if b == 'IEF' else 'gold_proxy').get('source_id')}",
                                            "window_start_date": start_day, "window_end_date": end_day,
                                            "window_observation_count": obs_count,
                                            "raw_sha256": hashlib.sha256(f"{prov_a.get('raw_sha256')}|{prov_b.get('raw_sha256')}".encode()).hexdigest()}
            features[feature] = _record(corr_value, f"{a}/{b} Yahoo return proxies",
                                        "UNVERIFIED_VENDOR_PROXY", _obs_day, asof,
                                        provenance=corr_provenance)
            histories[feature] = []
        else:
            features[feature] = {"value": None, "status": "INSUFFICIENT_DATA",
                "source_id": "UNKNOWN", "ticker": f"{a}|{b}", "source": "joint price returns",
                "observation_date": None, "published_at": None, "retrieved_at": None,
                "raw_sha256": None, "quality": "INSUFFICIENT_DATA", "license_status": "UNKNOWN",
                "window_observation_count": len(common_days)}
    if all(x is not None for x in (stock, bond, gold)) and window is not None:
        quality = "UNVERIFIED_VENDOR_PROXY"
        joint_date = common_days[-1]
        joint_stale = any((date.fromisoformat(asof)-date.fromisoformat(joint_date)).days > 5 for _ in (0,))
        features["synchronized_three_asset_down_20d"] = _record(all(x < 0 for x in (stock,bond,gold)),
            "NDX / IEF / GLD proxies", quality, joint_date, asof, joint_stale,
            {**window_provenance, "window_start_date": window[0], "window_end_date": window[1],
             "window_observation_count": len(common_days[-21:])})
        features["synchronized_three_asset_loss_5pct"] = _record(all(x <= -0.05 for x in (stock,bond,gold)),
            "NDX / IEF / GLD proxies", quality, joint_date, asof, joint_stale,
            {**window_provenance, "window_start_date": window[0], "window_end_date": window[1],
             "window_observation_count": len(common_days[-21:])})
    else:
        for feature in ("synchronized_three_asset_down_20d", "synchronized_three_asset_loss_5pct"):
            features[feature] = {"value": None, "status": "INSUFFICIENT_DATA",
                "source_id": "UNKNOWN", "ticker": "NDX|IEF|GLD", "source": "joint price returns",
                "observation_date": None, "published_at": None, "retrieved_at": None,
                "raw_sha256": None, "quality": "INSUFFICIENT_DATA", "license_status": "UNKNOWN",
                "window_observation_count": len(common_days),
                "reason": "Fewer than 21 common valid positive-price dates."}
    return features, histories
