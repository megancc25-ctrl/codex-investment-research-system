"""Deterministic signals using only observed closes at or before the signal date."""
import math
import statistics
from datetime import date

def mean(x):
    return sum(x)/len(x)

def evaluate(prices, asof, constituents=()):
    dates = sorted(d for d in set(prices.get("NDX", {})) & set(prices.get("SOX", {})) if d <= asof)
    if len(dates) < 201 or dates[-1] != asof:
        raise ValueError("Need 201 common NDX/SOX sessions through asof")
    n = [prices["NDX"][d] for d in dates]
    s = [prices["SOX"][d] for d in dates]
    ndx_trend = n[-1] / mean(n[-200:]) - 1
    sox_trend = s[-1] / mean(s[-200:]) - 1
    relative20 = (s[-1] / s[-21]) / (n[-1] / n[-21]) - 1
    logreturns = [math.log(n[i]/n[i-1]) for i in range(len(n)-20,len(n))]
    vol = statistics.stdev(logreturns) * math.sqrt(252)
    available = []
    for symbol in constituents:
        seq = prices.get(symbol, {})
        if all(d in seq for d in dates[-50:]):
            available.append(symbol)
    breadth = None
    if available:
        breadth = sum(prices[sym][asof] > mean([prices[sym][d] for d in dates[-50:]]) for sym in available)/len(available)
    trend_bad = int(ndx_trend < 0) + int(sox_trend < 0)
    fast_bad = int(relative20 < -0.05) + int(vol > 0.30) + int(breadth is not None and breadth < 0.40)
    level = 3 if trend_bad == 2 and fast_bad >= 2 else 2 if trend_bad >= 1 and fast_bad >= 1 else 1 if trend_bad >= 1 or fast_bad >= 1 else 0
    weight = {0:1.00,1:0.80,2:0.50,3:0.20}[level]
    return {
        "asof": str(asof), "level": level, "model_risk_weight": weight,
        "ndx_vs_200dma": round(ndx_trend,5), "sox_vs_200dma": round(sox_trend,5),
        "sox_relative_ndx_20d": round(relative20,5),
        "ndx_20d_realized_vol": round(vol,5),
        "breadth_50dma": None if breadth is None else round(breadth,5),
        "breadth_coverage": f"{len(available)}/{len(constituents)}",
        "status": "RESEARCH_UNVALIDATED"
    }

def drawdown(equity):
    peak = 0
    worst = 0.0
    for x in equity:
        peak = max(peak,x)
        worst = min(worst,x/peak-1)
    return worst
