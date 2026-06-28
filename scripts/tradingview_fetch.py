"""TradingView 行情：TAIEX、台指期 TXF1!。"""

from __future__ import annotations

from curl_cffi import requests

TV_SCAN_GLOBAL = "https://scanner.tradingview.com/global/scan"
TV_SCAN_TAIWAN = "https://scanner.tradingview.com/taiwan/scan"

TV_TAIEX_SYMBOL = "TWSE:IX0001"
TV_TAIEX_DISPLAY = "INDEX:TAIEX"
TV_TAIEX_URL = "https://www.tradingview.com/symbols/INDEX-TAIEX/"

TV_TX_SYMBOL = "TAIFEX:TXF1!"
TV_TX_URL = "https://www.tradingview.com/symbols/TAIFEX-TXF1!/"

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


def _scan_symbol(symbol: str, *, scan_url: str = TV_SCAN_GLOBAL) -> dict:
    payload = {
        "symbols": {"tickers": [symbol], "query": {"types": []}},
        "columns": _SCAN_COLUMNS,
    }
    resp = requests.post(scan_url, json=payload, impersonate="chrome", timeout=20)
    resp.raise_for_status()
    body = resp.json()

    rows = body.get("data") or []
    if not rows:
        raise ValueError(f"TradingView 查無 {symbol}")

    row = rows[0]["d"]
    close, lp, ch, change, open_, high, low, volume, description = row
    price = lp if lp is not None else close
    if price is None:
        raise ValueError(f"TradingView 無有效價格：{symbol}")

    return {
        "symbol": symbol,
        "name": description or symbol,
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
    }


def fetch_taiex() -> dict:
    """取得 TradingView TAIEX（INDEX-TAIEX / TWSE:IX0001）。"""
    data = _scan_symbol(TV_TAIEX_SYMBOL, scan_url=TV_SCAN_TAIWAN)
    return {
        **data,
        "display": TV_TAIEX_DISPLAY,
        "url": TV_TAIEX_URL,
    }


def fetch_tx_futures() -> dict:
    """取得 TradingView 台指期近月 (TXF1!)。"""
    data = _scan_symbol(TV_TX_SYMBOL, scan_url=TV_SCAN_GLOBAL)
    return {
        **data,
        "url": TV_TX_URL,
    }
