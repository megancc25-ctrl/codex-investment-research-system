"""Point-in-time six-module walk-forward risk research backtest.

No training on holdout, no execution of trades. Accepts historical evidence
only with independently verified release timestamps and explicit prices.
"""
from datetime import date
from .factors_v2 import calculate_modules
from .risk_v2 import score_v2

def future_drawdown(prices, start, horizon):
    """Max peak-to-trough drawdown including starting close."""
    window = prices[start:start+horizon+1]
    if len(window) < horizon+1:
        return None
    peak = window[0]
    worst = 0.0
    for price in window[1:]:
        peak = max(peak,price)
        worst = min(worst,price/peak-1)
    return worst

def walk_forward(sessions, evidence_by_date, prices, horizons=(20,40,60),
                 min_history=60):
    """No fabricated missing factor values; returns evidence coverage and
    descriptive forward drawdowns, not validated forecasting accuracy.
    sessions: sorted dates, evidence: per-date records with release proofs.
    """
    if len(sessions)!=len(prices) or sorted(set(sessions))!=list(sessions):
        raise ValueError("Sessions and prices must be unique, ordered and aligned")
    if any(p<=0 for p in prices) or any(h<1 for h in horizons):
        raise ValueError("Invalid prices/horizons")
    rows=[]
    for i,day in enumerate(sessions):
        date.fromisoformat(day)
        decision_at=day+"T23:59:59Z" # after US cash close, conservative UTC cutoff
        modules, diagnostics=calculate_modules(
            evidence_by_date.get(day,{}),decision_at,min_history,mode="historical")
        risk=score_v2(modules)
        rows.append({"date":day,"score":risk["score"],
                     "status":risk["status"],
                     "verified_coverage_pct":risk["verified_coverage_pct"],
                     "module_diagnostics":diagnostics,
                     "future_drawdown":{str(h):future_drawdown(prices,i,h) for h in horizons}})
    complete=[r for r in rows if r["score"] is not None]
    return {"sessions":len(rows),"fully_scored":len(complete),
            "score_coverage":round(len(complete)/len(rows),4) if rows else 0,
            "rows":rows,
            "limitations":["No survivorship-free historical constituent guarantee",
                           "No EPS consensus reconstruction from SEC GAAP",
                           "No calibrated predictive accuracy or trade strategy",
                           "Historical releases require independent verification"]}
