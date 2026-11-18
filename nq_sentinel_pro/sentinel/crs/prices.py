"""Daily public-market proxy prices. Yahoo/yfinance observations remain unverified."""
from __future__ import annotations
from datetime import datetime, timezone

TICKERS = {"ndx": "^NDX", "sox": "^SOX", "bond_total_return_proxy": "IEF",
           "gold_proxy": "GLD", "dxy_proxy": "DX-Y.NYB"}

def fetch_prices(asof, period="10y", opener=None):
    import yfinance as yf
    result, diagnostics = {}, {}
    for key, ticker in TICKERS.items():
        try:
            frame = yf.Ticker(ticker).history(period=period, auto_adjust=True, actions=False)
            if frame is None or frame.empty:
                raise ValueError("Empty vendor series")
            rows = {}
            for timestamp, bar in frame.iterrows():
                day = str(timestamp.date())
                close = float(bar["Close"])
                if day <= asof and close > 0 and close == close and abs(close) != float("inf"):
                    rows[day] = close
            if not rows:
                raise ValueError("No valid close on or before as-of date")
            result[key] = rows
            diagnostics[key] = {"status": "AVAILABLE", "ticker": ticker,
                                "source": "Yahoo Finance via yfinance",
                                "quality": "UNVERIFIED_VENDOR_PROXY", "latest_date": max(rows),
                                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                "note": "Price/total-return proxy only; vendor history is not independently reconciled."}
        except Exception as exc:
            diagnostics[key] = {"status": "MISSING", "ticker": ticker, "reason": str(exc)[:240],
                                "quality": "UNVERIFIED_VENDOR_PROXY"}
    return result, diagnostics
