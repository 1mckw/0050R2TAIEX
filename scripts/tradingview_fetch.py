"""TradingView 台指期 TXF1! 行情。"""

from __future__ import annotations

from curl_cffi import requests

TV_TX_SYMBOL = "TAIFEX:TXF1!"
TV_TX_URL = "https://www.tradingview.com/symbols/TAIFEX-TXF1!/"
TV_SCAN_URL = "https://scanner.tradingview.com/global/scan"

_SCAN_COLUMNS = [
    "close",
    "lp",
    "ch",
    "change",
    "open",
    "high",
    "low",
    "volume",
    "description",
]


def fetch_tx_futures() -> dict:
    """取得 TradingView 台指期近月 (TXF1!) 報價。"""
    payload = {
        "symbols": {"tickers": [TV_TX_SYMBOL], "query": {"types": []}},
        "columns": _SCAN_COLUMNS,
    }
    resp = requests.post(TV_SCAN_URL, json=payload, impersonate="chrome", timeout=20)
    resp.raise_for_status()
    body = resp.json()

    rows = body.get("data") or []
    if not rows:
        raise ValueError(f"TradingView 查無 {TV_TX_SYMBOL}")

    row = rows[0]["d"]
    close, lp, ch, change, open_, high, low, volume, description = row
    price = lp if lp is not None else close
    if price is None:
        raise ValueError("TradingView 無有效台指期價格")

    return {
        "symbol": TV_TX_SYMBOL,
        "name": description or "TAIEX FUTURES",
        "price": round(float(price), 2),
        "close": round(float(close), 2) if close is not None else None,
        "lp": round(float(lp), 2) if lp is not None else None,
        "change": round(float(ch), 2) if ch is not None else None,
        "change_pct": round(float(change), 4) if change is not None else None,
        "open": round(float(open_), 2) if open_ is not None else None,
        "high": round(float(high), 2) if high is not None else None,
        "low": round(float(low), 2) if low is not None else None,
        "volume": int(volume) if volume is not None else None,
        "source": "TradingView",
        "url": TV_TX_URL,
    }
