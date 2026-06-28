"""
TAIEX / 台指期 → 0050反 價格換算

0050反 與台指期（追蹤 TAIEX）高度相關，可用歷史價格關係推算：
  - ratio：當前倍率法（0050反 / TAIEX）
  - regression：線性迴歸（0050反 = α + β × TAIEX）
  - spread：價差法（0050反 = 參考 0050反 + β × (TAIEX - 參考 TAIEX)）
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf

Method = Literal["ratio", "regression", "spread"]


@dataclass(frozen=True)
class ConversionResult:
    taiex: float
    implied_0050反: float
    method: Method
    ratio: float | None = None
    alpha: float | None = None
    beta: float | None = None
    reference_taiex: float | None = None
    reference_0050反: float | None = None


def fetch_prices(
    lookback_days: int = 60,
    end: datetime | None = None,
) -> pd.DataFrame:
    """取得 TAIEX 與 0050反 歷史收盤價。"""
    end = end or datetime.now()
    start = end - timedelta(days=lookback_days + 10)

    taiex = yf.download("^TWII", start=start, end=end, progress=False)["Close"]
    etf = yf.download("00632R.TW", start=start, end=end, progress=False)["Close"]

    if isinstance(taiex, pd.DataFrame):
        taiex = taiex.squeeze()
    if isinstance(etf, pd.DataFrame):
        etf = etf.squeeze()

    df = pd.DataFrame({"taiex": taiex, "etf_0050反": etf}).dropna()
    if df.empty:
        raise ValueError("無法取得 TAIEX 或 0050反 歷史資料，請確認網路與代碼。")
    return df.tail(lookback_days)


def fit_regression(df: pd.DataFrame) -> tuple[float, float]:
    """OLS: etf_0050反 = alpha + beta * taiex"""
    x = df["taiex"].to_numpy(dtype=float)
    y = df["etf_0050反"].to_numpy(dtype=float)
    beta, alpha = np.polyfit(x, y, 1)
    return float(alpha), float(beta)


def current_ratio(df: pd.DataFrame) -> float:
    latest = df.iloc[-1]
    return float(latest["etf_0050反"] / latest["taiex"])


def taiex_to_0050反(
    taiex_price: float,
    df: pd.DataFrame,
    method: Method = "regression",
) -> ConversionResult:
    """
    將 TAIEX 點位換算為對應 0050反 價格。

    method:
      - ratio:       0050反 = TAIEX × (最新 0050反 / 最新 TAIEX)
      - regression:  0050反 = α + β × TAIEX（全樣本迴歸）
      - spread:      0050反 = 參考 0050反 + β × (TAIEX - 參考 TAIEX)
    """
    alpha, beta = fit_regression(df)
    ref = df.iloc[-1]
    ref_taiex = float(ref["taiex"])
    ref_0050反 = float(ref["etf_0050反"])
    ratio = current_ratio(df)

    if method == "ratio":
        implied = taiex_price * ratio
        return ConversionResult(
            taiex=taiex_price,
            implied_0050反=implied,
            method=method,
            ratio=ratio,
            reference_taiex=ref_taiex,
            reference_0050反=ref_0050反,
        )

    if method == "regression":
        implied = alpha + beta * taiex_price
        return ConversionResult(
            taiex=taiex_price,
            implied_0050反=implied,
            method=method,
            alpha=alpha,
            beta=beta,
            reference_taiex=ref_taiex,
            reference_0050反=ref_0050反,
        )

    if method == "spread":
        implied = ref_0050反 + beta * (taiex_price - ref_taiex)
        return ConversionResult(
            taiex=taiex_price,
            implied_0050反=implied,
            method=method,
            beta=beta,
            reference_taiex=ref_taiex,
            reference_0050反=ref_0050反,
        )

    raise ValueError(f"未知 method: {method}")


def tx_to_0050反(
    tx_price: float,
    df: pd.DataFrame,
    method: Method = "spread",
    basis: float = 0.0,
) -> ConversionResult:
    """
    台指期 → 0050反 換算。

    台指期與 TAIEX 近似：TAIEX ≈ TX - basis（basis 為期貨基差，預設 0）。
    先將 TX 換成隱含 TAIEX，再套用 taiex_to_0050反。
    """
    implied_taiex = tx_price - basis
    result = taiex_to_0050反(implied_taiex, df, method=method)
    return ConversionResult(
        taiex=implied_taiex,
        implied_0050反=result.implied_0050反,
        method=result.method,
        ratio=result.ratio,
        alpha=result.alpha,
        beta=result.beta,
        reference_taiex=result.reference_taiex,
        reference_0050反=result.reference_0050反,
    )


def render_html(
    df: pd.DataFrame,
    result: ConversionResult,
    *,
    input_price: float,
    is_tx: bool = False,
    basis: float = 0.0,
    method: Method = "spread",
    generated_at: datetime | None = None,
) -> str:
    """產生 HTML 報表。"""
    generated_at = generated_at or datetime.now()
    latest = df.iloc[-1]
    alpha, beta = fit_regression(df)
    ratio = current_ratio(df)
    ref_taiex = float(result.reference_taiex or latest["taiex"])
    ref_0050反 = float(result.reference_0050反 or latest["etf_0050反"])

    scenarios: list[tuple[str, float, float]] = []
    for pct in (-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03):
        t = ref_taiex * (1 + pct)
        s = taiex_to_0050反(t, df, method=method)
        label = f"{pct*100:+.0f}%" if pct != 0 else "基準"
        scenarios.append((label, t, s.implied_0050反))

    grid_levels = [ref_taiex * f for f in (0.90, 0.95, 1.0, 1.05, 1.10)]
    grid_rows = [
        (t, taiex_to_0050反(t, df, method=method).implied_0050反) for t in grid_levels
    ]

    input_label = "台指期" if is_tx else "TAIEX"
    implied_label = (
        f"台指期 {input_price:,.0f}（基差 {basis:,.0f}）→ 隱含 TAIEX {result.taiex:,.2f}"
        if is_tx
        else f"TAIEX {input_price:,.2f}"
    )

    method_desc = {
        "spread": "價差法：0050反 = 參考 0050反 + β × (TAIEX − 參考 TAIEX)",
        "ratio": "倍率法：0050反 = TAIEX × (最新 0050反 / 最新 TAIEX)",
        "regression": "迴歸法：0050反 = α + β × TAIEX",
    }[method]

    scenario_rows = "\n".join(
        f"<tr><td>{lbl}</td><td class='num'>{t:,.2f}</td>"
        f"<td class='num'>{p:.2f}</td></tr>"
        for lbl, t, p in scenarios
    )
    grid_html = "\n".join(
        f"<tr><td class='num'>{t:,.2f}</td><td class='num'>{p:.2f}</td></tr>"
        for t, p in grid_rows
    )

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TAIEX → 0050反 換算</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --border: #2d3a4f;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --green: #3dd68c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Microsoft JhengHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }}
    .wrap {{ max-width: 900px; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 8px; }}
    .sub {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 24px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 20px;
    }}
    .card .label {{ color: var(--muted); font-size: 0.85rem; }}
    .card .value {{ font-size: 1.6rem; font-weight: 600; margin-top: 4px; }}
    .card.highlight .value {{ color: var(--accent); }}
    .card.result .value {{ color: var(--green); }}
    section {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 20px;
    }}
    section h2 {{ font-size: 1rem; margin: 0 0 12px; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-weight: 500; }}
    td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .meta {{ color: var(--muted); font-size: 0.85rem; }}
    .formula {{ font-family: Consolas, monospace; font-size: 0.9rem; color: var(--accent); }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>TAIEX / 台指期 → 0050反 換算</h1>
    <p class="sub">產生時間：{generated_at.strftime("%Y-%m-%d %H:%M:%S")}　｜　樣本 {df.index[0].date()} ~ {df.index[-1].date()}（{len(df)} 日）</p>

    <div class="cards">
      <div class="card">
        <div class="label">最新 TAIEX</div>
        <div class="value">{latest['taiex']:,.2f}</div>
      </div>
      <div class="card">
        <div class="label">最新 0050反</div>
        <div class="value">{latest['etf_0050反']:.2f}</div>
      </div>
      <div class="card highlight">
        <div class="label">輸入 {input_label}</div>
        <div class="value">{input_price:,.2f}</div>
      </div>
      <div class="card result">
        <div class="label">推算 0050反</div>
        <div class="value">{result.implied_0050反:.2f}</div>
      </div>
    </div>

    <section>
      <h2>換算結果</h2>
      <p>{implied_label}</p>
      <p class="formula">{method_desc}</p>
      <table>
        <tr><th>項目</th><th class="num">數值</th></tr>
        <tr><td>方法</td><td class="num">{method}</td></tr>
        <tr><td>參考 TAIEX</td><td class="num">{ref_taiex:,.2f}</td></tr>
        <tr><td>參考 0050反</td><td class="num">{ref_0050反:.2f}</td></tr>
        <tr><td>倍率 (0050反/TAIEX)</td><td class="num">{ratio:.6f}</td></tr>
        <tr><td>α</td><td class="num">{alpha:.4f}</td></tr>
        <tr><td>β</td><td class="num">{beta:.6f}</td></tr>
      </table>
    </section>

    <section>
      <h2>TAIEX 情境（相對基準 ±%）</h2>
      <table>
        <tr><th>變動</th><th class="num">TAIEX</th><th class="num">推算 0050反</th></tr>
        {scenario_rows}
      </table>
    </section>

    <section>
      <h2>TAIEX 價位對照表</h2>
      <table>
        <tr><th class="num">TAIEX</th><th class="num">推算 0050反</th></tr>
        {grid_html}
      </table>
    </section>

    <p class="meta">資料來源：Yahoo Finance（^TWII、00632R.TW）。僅供參考，非投資建議。</p>
  </div>
</body>
</html>"""


def write_html_report(
    output_path: str,
    df: pd.DataFrame,
    result: ConversionResult,
    *,
    input_price: float,
    is_tx: bool = False,
    basis: float = 0.0,
    method: Method = "spread",
) -> str:
    html = render_html(
        df,
        result,
        input_price=input_price,
        is_tx=is_tx,
        basis=basis,
        method=method,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def format_result(result: ConversionResult, label: str = "TAIEX") -> str:
    lines = [
        f"{label}: {result.taiex:,.2f}",
        f"推算 0050反: {result.implied_0050反:.2f} 元",
        f"方法: {result.method}",
    ]
    if result.reference_taiex is not None:
        lines.append(
            f"參考 TAIEX: {result.reference_taiex:,.2f} | 參考 0050反: {result.reference_0050反:.2f}"
        )
    if result.ratio is not None:
        lines.append(f"倍率 (0050反/TAIEX): {result.ratio:.6f}")
    if result.beta is not None:
        extra = f"α={result.alpha:.4f}, " if result.alpha is not None else ""
        lines.append(f"迴歸: {extra}β={result.beta:.6f}")
    return "\n".join(lines)


def main() -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="TAIEX / 台指期 → 0050反 價格換算")
    parser.add_argument(
        "price",
        type=float,
        nargs="?",
        help="TAIEX 點位或台指期價格",
    )
    parser.add_argument(
        "--tx",
        action="store_true",
        help="輸入為台指期價格（預設為 TAIEX）",
    )
    parser.add_argument(
        "--basis",
        type=float,
        default=0.0,
        help="期貨基差：TAIEX ≈ TX - basis（僅 --tx 時有效）",
    )
    parser.add_argument(
        "--method",
        choices=["ratio", "regression", "spread"],
        default="spread",
        help="換算方法（預設 spread，適合短線價差追蹤）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=60,
        help="歷史樣本天數（預設 60）",
    )
    parser.add_argument(
        "--html",
        metavar="FILE",
        help="輸出 HTML 報表至指定檔案",
    )
    args = parser.parse_args()

    df = fetch_prices(lookback_days=args.days)
    latest = df.iloc[-1]

    price = args.price
    if price is None:
        price = float(latest["taiex"])

    if args.tx:
        result = tx_to_0050反(price, df, method=args.method, basis=args.basis)
    else:
        result = taiex_to_0050反(price, df, method=args.method)

    if args.html:
        out = write_html_report(
            args.html,
            df,
            result,
            input_price=price,
            is_tx=args.tx,
            basis=args.basis,
            method=args.method,
        )
        print(f"HTML 已輸出：{out}")
        return

    print(f"最新 TAIEX: {latest['taiex']:,.2f} | 最新 0050反: {latest['etf_0050反']:.2f}")
    print(f"樣本期間: {df.index[0].date()} ~ {df.index[-1].date()} ({len(df)} 日)")
    print("-" * 50)

    if args.tx:
        print(format_result(result, label=f"台指期 {price:,.0f} (隱含 TAIEX)"))
    else:
        print(format_result(result))

    # 示範：TAIEX ±1% 對應 0050反
    print("-" * 50)
    for pct in (-0.01, 0.01):
        scenario_taiex = result.reference_taiex * (1 + pct) if result.reference_taiex else price * (1 + pct)
        scenario = taiex_to_0050反(scenario_taiex, df, method=args.method)
        sign = "+" if pct > 0 else ""
        print(f"TAIEX {sign}{pct*100:.0f}% → 0050反 ≈ {scenario.implied_0050反:.2f}")


if __name__ == "__main__":
    main()
