"""匯出網站用的行情 JSON。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taiex_to_0050 import (  # noqa: E402
    current_ratio,
    fetch_prices,
    fit_regression,
    taiex_to_0050反,
)


def export(lookback_days: int = 60) -> dict:
    df = fetch_prices(lookback_days=lookback_days)
    latest = df.iloc[-1]
    alpha, beta = fit_regression(df)
    ratio = current_ratio(df)
    ref_taiex = float(latest["taiex"])
    ref_etf = float(latest["etf_0050反"])

    base = taiex_to_0050反(ref_taiex, df, method="spread")
    scenarios = []
    for pct in (-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03):
        t = ref_taiex * (1 + pct)
        r = taiex_to_0050反(t, df, method="spread")
        scenarios.append(
            {
                "label": f"{pct * 100:+.0f}%" if pct != 0 else "基準",
                "taiex": round(t, 2),
                "etf": round(r.implied_0050反, 2),
            }
        )

    history = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "taiex": round(float(row["taiex"]), 2),
            "etf": round(float(row["etf_0050反"]), 2),
        }
        for idx, row in df.iterrows()
    ]

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": {"taiex": "^TWII", "etf": "00632R.TW", "etf_name": "0050反"},
        "latest": {
            "taiex": round(ref_taiex, 2),
            "etf": round(ref_etf, 2),
        },
        "sample": {
            "start": df.index[0].strftime("%Y-%m-%d"),
            "end": df.index[-1].strftime("%Y-%m-%d"),
            "days": len(df),
        },
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", default="docs/data.json")
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    payload = export(lookback_days=args.days)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫入 {out}（TAIEX {payload['latest']['taiex']} | 0050反 {payload['latest']['etf']}）")


if __name__ == "__main__":
    main()
