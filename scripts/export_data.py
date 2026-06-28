"""匯出網站用的行情 JSON。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from taiex_to_0050 import ETF_PRODUCTS, fetch_prices, fit_regression, current_ratio, taiex_to_etf  # noqa: E402
from tradingview_fetch import TV_TX_SYMBOL, TV_TX_URL, fetch_tx_futures  # noqa: E402


def _product_payload(df, name: str) -> dict:
    col = ETF_PRODUCTS[name]["column"]
    alpha, beta = fit_regression(df, name)
    ratio = current_ratio(df, name)
    ref_taiex = float(df.iloc[-1]["taiex"])
    ref_etf = float(df.iloc[-1][col])

    scenarios = []
    for pct in (-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03):
        t = ref_taiex * (1 + pct)
        r = taiex_to_etf(t, df, name, method="spread")
        scenarios.append(
            {
                "label": f"{pct * 100:+.0f}%" if pct != 0 else "基準",
                "taiex": round(t, 2),
                "etf": round(r.implied_etf, 2),
            }
        )

    history = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "taiex": round(float(row["taiex"]), 2),
            "etf": round(float(row[col]), 2),
        }
        for idx, row in df.iterrows()
    ]

    return {
        "symbol": ETF_PRODUCTS[name]["symbol"],
        "latest": round(ref_etf, 2),
        "model": {
            "method": "spread",
            "alpha": round(alpha, 6),
            "beta": round(beta, 8),
            "ratio": round(ratio, 8),
            "ref_taiex": round(ref_taiex, 2),
            "ref_etf": round(ref_etf, 2),
        },
        "scenarios": scenarios,
        "history": history,
    }


def export(lookback_days: int = 60) -> dict:
    df = fetch_prices(lookback_days=lookback_days)
    latest = df.iloc[-1]
    ref_taiex = round(float(latest["taiex"]), 2)

    tx_payload = None
    tx_error = None
    try:
        tx_payload = fetch_tx_futures()
    except Exception as exc:
        tx_error = str(exc)

    latest_out = {
        "taiex": ref_taiex,
        "0050": round(float(latest["etf_0050"]), 2),
        "0050反": round(float(latest["etf_0050_inv"]), 2),
    }

    if tx_payload:
        latest_out["tx"] = tx_payload["price"]
        latest_out["basis"] = round(tx_payload["price"] - ref_taiex, 2)

    products = {name: _product_payload(df, name) for name in ETF_PRODUCTS}

    sources = {
        "taiex": {"provider": "Yahoo Finance", "symbol": "^TWII"},
        "0050": {"provider": "Yahoo Finance", "symbol": "0050.TW"},
        "0050反": {"provider": "Yahoo Finance", "symbol": "00632R.TW"},
    }
    if tx_payload:
        sources["tx"] = {
            "provider": "TradingView",
            "symbol": TV_TX_SYMBOL,
            "url": TV_TX_URL,
        }

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": {"taiex": "^TWII", "tx": TV_TX_SYMBOL},
        "latest": latest_out,
        "tx": tx_payload,
        "tx_error": tx_error,
        "sources": sources,
        "sample": {
            "start": df.index[0].strftime("%Y-%m-%d"),
            "end": df.index[-1].strftime("%Y-%m-%d"),
            "days": len(df),
        },
        "products": products,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", default="docs/data.json")
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    payload = export(lookback_days=args.days)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lat = payload["latest"]
    tx_part = f" | TX {lat['tx']}" if lat.get("tx") is not None else ""
    if payload.get("tx_error"):
        tx_part += f" (TX 失敗: {payload['tx_error']})"
    print(f"已寫入 {out}（TAIEX {lat['taiex']}{tx_part} | 0050 {lat['0050']} | 0050反 {lat['0050反']}）")


if __name__ == "__main__":
    main()
