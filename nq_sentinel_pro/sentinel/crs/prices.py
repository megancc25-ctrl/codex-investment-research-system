"""Daily public-market proxy prices. Yahoo/yfinance observations remain unverified."""
from __future__ import annotations
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

TICKERS = {"ndx": "^NDX", "sox": "^SOX", "bond_total_return_proxy": "IEF",
           "gold_proxy": "GLD", "dxy_proxy": "DX-Y.NYB"}

def fetch_prices(asof, period="10y", opener=None, timeout=10):
    import yfinance as yf
    result, diagnostics = {}, {}
    def fetch_one(key, ticker):
        try:
            frame = yf.Ticker(ticker).history(period=period, auto_adjust=True, actions=False, timeout=timeout)
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
            return key, rows, {"status": "AVAILABLE", "ticker": ticker,
                                "source": "Yahoo Finance via yfinance",
                                "quality": "UNVERIFIED_VENDOR_PROXY", "latest_date": max(rows),
                                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                "note": "Price/total-return proxy only; vendor history is not independently reconciled."}
        except Exception as exc:
            return key, None, {"status": "MISSING", "ticker": ticker, "reason": str(exc)[:240],
                               "quality": "UNVERIFIED_VENDOR_PROXY"}
    with ThreadPoolExecutor(max_workers=min(5, len(TICKERS))) as pool:
        futures = [pool.submit(fetch_one, key, ticker) for key, ticker in TICKERS.items()]
        for future in as_completed(futures):
            key, rows, diagnostic = future.result()
            if rows is not None:
                result[key] = rows
            diagnostics[key] = diagnostic
    return result, diagnostics
