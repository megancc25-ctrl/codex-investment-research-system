"""Independent combination alerts. Alerts are not added a second time to the weighted score."""
def _get(features, key):
    item = features.get(key)
    return item.get("value") if isinstance(item, dict) else item

def _yes(value):
    return value is not None and bool(value)

def evaluate_alerts(features, metrics=None):
    metrics = metrics or {}
    n10, real10 = _get(features, "ust10y_change_20d_bp"), _get(features, "real10y_change_20d_bp")
    usd, gold_loss = _get(features, "usd_20d_change_pct"), _get(features, "gold_drawdown_20d")
    inflation_flags = [n10 is not None and n10 >= 30, real10 is not None and real10 >= 20,
                       usd is not None and usd >= 0.02, gold_loss is not None and gold_loss >= 0.05]
    n_inflation = sum(inflation_flags)
    inflation = ("RED_CANDIDATE" if n_inflation >= 3 and inflation_flags[1] and inflation_flags[3]
                 else "YELLOW" if n_inflation >= 2 else
                 "CLEAR" if all(x is not None for x in (n10, real10, usd, gold_loss)) else "INSUFFICIENT_DATA")

    hy_change, hy_level = _get(features, "hy_oas_change_20d_bp"), _get(features, "hy_oas_bp")
    ig_level, eq_loss = _get(features, "ig_oas_bp"), _get(features, "ndx_return_20d")
    credit_flags = [hy_change is not None and hy_change >= 75,
                    ig_level is not None and ig_level >= 150,
                    _yes(metrics.get("cdx_hy_widening")),
                    eq_loss is not None and eq_loss <= -0.05]
    n_credit = sum(credit_flags)
    credit = ("SEVERE_WATCH" if hy_level is not None and hy_level >= 650 else
              "RED_CANDIDATE" if n_credit >= 3 and credit_flags[0] else
              "YELLOW" if n_credit >= 2 else
              "CLEAR" if all(x is not None for x in (hy_change, ig_level, eq_loss)) else "INSUFFICIENT_DATA")

    sync_value = _get(features, "synchronized_three_asset_down_20d")
    severe_value = _get(features, "synchronized_three_asset_loss_5pct")
    sync = bool(sync_value) if sync_value is not None else False
    severe_sync = bool(severe_value) if severe_value is not None else False
    repo_bad = _yes(metrics.get("repo_extreme"))
    funding_bad = _yes(metrics.get("funding_market_failure")) or _yes(metrics.get("margin_stress"))
    liquidity = ("RED_CANDIDATE" if sync and (repo_bad or funding_bad) else
                 "CROSS_ASSET_SELL_OFF" if sync else
                 "CLEAR" if sync_value is not None else "INSUFFICIENT_DATA")

    ai_keys = ("cloud_capex_yoy_pct", "cloud_operating_cash_flow_yoy_pct",
               "free_cash_flow_yoy_pct", "gpu_rental_price_yoy_pct",
               "semiconductor_estimate_revision_pct")
    ai_missing = [k for k in ai_keys if _get(features, k) is None]
    ai_values = {k: _get(features, k) for k in ai_keys if _get(features, k) is not None}
    ai = "INSUFFICIENT_DATA"
    if not ai_missing:
        deteriorations = sum([
            ai_values["cloud_capex_yoy_pct"] > ai_values["cloud_operating_cash_flow_yoy_pct"],
            ai_values["free_cash_flow_yoy_pct"] < 0,
            ai_values["gpu_rental_price_yoy_pct"] < 0,
            ai_values["semiconductor_estimate_revision_pct"] < 0,
        ])
        ai = "RED_CANDIDATE" if deteriorations >= 3 else "YELLOW" if deteriorations >= 2 else "CLEAR"

    return {
        "inflation_shock": {"state": inflation, "evidence_count": n_inflation, "required": 3,
                            "evidence": [k for k, ok in zip(("nominal_yield", "real_yield", "dollar", "gold"), inflation_flags) if ok]},
        "credit_risk": {"state": credit, "evidence_count": n_credit, "required": 3,
                        "evidence": [k for k, ok in zip(("hy_widening", "ig_wide", "cdx_hy_widening", "equity_down"), credit_flags) if ok]},
        "liquidity_crisis": {"state": liquidity, "synchronized_three_asset_loss": sync,
                             "severe_synchronized_loss": severe_sync,
                             "evidence": [k for k, ok in (("stock_bond_gold_sync", sync),
                             ("repo_extreme", repo_bad), ("funding_or_margin_stress", funding_bad)) if ok],
                             "rule": "Requires stock, bond and gold all down plus a confirmed repo/funding/margin anomaly."},
        "ai_capital_return": {"state": ai, "missing_inputs": ai_missing, "evidence": ai_values,
                              "adds_to_crs_score": False,
                              "note": "Satellite alert; GPU rental prices are not fabricated and do not enter base CRS."},
    }
