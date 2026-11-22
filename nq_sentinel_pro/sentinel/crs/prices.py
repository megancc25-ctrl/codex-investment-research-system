"""Daily public-market proxy prices. Yahoo/yfinance observations remain unverified."""
from __future__ import annotations

TICKERS = {"ndx": "^NDX", "sox": "^SOX", "bond_total_return_proxy": "IEF",
           "gold_proxy": "GLD", "dxy_proxy": "DX-Y.NYB"}

def fetch_prices(asof, period="10y", opener=None):
    # No vendor price license has been admitted in the engineering phase.
    return {}, {key: {"status": "MISSING", "ticker": ticker,
        "source_id": f"yahoo:{ticker}", "license_status": "REVIEW_REQUIRED",
        "quality": "LICENSE_BLOCKED", "reason": "LICENSE_BLOCKED: live price collection disabled"}
        for key, ticker in TICKERS.items()}
