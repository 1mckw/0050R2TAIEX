"""
TAIEX / 台指期 → 0050、0050反 價格換算

0050、0050反 與台指期（追蹤 TAIEX）高度相關，可用歷史價格關係推算。
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

ETF_PRODUCTS: dict[str, dict[str, str]] = {
    "0050": {"symbol": "0050.TW", "column": "etf_0050"},
    "0050反": {"symbol": "00632R.TW", "column": "etf_0050_inv"},
}


@dataclass(frozen=True)
class ConversionResult:
    taiex: float
    implied_etf: float
    etf_name: str
    method: Method
    ratio: float | None = None
    alpha: float | None = None
    beta: float | None = None
    reference_taiex: float | None = None
    reference_etf: float | None = None


def fetch_prices(
    lookback_days: int = 60,
    end: datetime | None = None,
) -> pd.DataFrame:
    """取得 TAIEX、0050、0050反 歷史收盤價。"""
    end = end or datetime.now()
    start = end - timedelta(days=lookback_days + 10)

    taiex = yf.download("^TWII", start=start, end=end, progress=False)["Close"]
    etf_0050 = yf.download("0050.TW", start=start, end=end, progress=False)["Close"]
    etf_inv = yf.download("00632R.TW", start=start, end=end, progress=False)["Close"]

    if isinstance(taiex, pd.DataFrame):
        taiex = taiex.squeeze()
    if isinstance(etf_0050, pd.DataFrame):
        etf_0050 = etf_0050.squeeze()
    if isinstance(etf_inv, pd.DataFrame):
        etf_inv = etf_inv.squeeze()

    df = pd.DataFrame({"taiex": taiex, "etf_0050": etf_0050, "etf_0050_inv": etf_inv}).dropna()
    if df.empty:
        raise ValueError("無法取得 TAIEX 或 ETF 歷史資料，請確認網路與代碼。")
    return df.tail(lookback_days)


def _etf_column(etf_name: str) -> str:
    if etf_name not in ETF_PRODUCTS:
        raise ValueError(f"未知 ETF: {etf_name}，可選: {', '.join(ETF_PRODUCTS)}")
    return ETF_PRODUCTS[etf_name]["column"]


def fit_regression(df: pd.DataFrame, etf_name: str = "0050反") -> tuple[float, float]:
    col = _etf_column(etf_name)
    x = df["taiex"].to_numpy(dtype=float)
    y = df[col].to_numpy(dtype=float)
    beta, alpha = np.polyfit(x, y, 1)
    return float(alpha), float(beta)


def current_ratio(df: pd.DataFrame, etf_name: str = "0050反") -> float:
    col = _etf_column(etf_name)
    latest = df.iloc[-1]
    return float(latest[col] / latest["taiex"])


def taiex_to_etf(
    taiex_price: float,
    df: pd.DataFrame,
    etf_name: str = "0050反",
    method: Method = "spread",
) -> ConversionResult:
    col = _etf_column(etf_name)
    alpha, beta = fit_regression(df, etf_name)
    ref = df.iloc[-1]
    ref_taiex = float(ref["taiex"])
    ref_etf = float(ref[col])
    ratio = current_ratio(df, etf_name)

    if method == "ratio":
        implied = taiex_price * ratio
    elif method == "regression":
        implied = alpha + beta * taiex_price
    elif method == "spread":
        implied = ref_etf + beta * (taiex_price - ref_taiex)
    else:
        raise ValueError(f"未知 method: {method}")

    return ConversionResult(
        taiex=taiex_price,
        implied_etf=implied,
        etf_name=etf_name,
        method=method,
        ratio=ratio if method == "ratio" else None,
        alpha=alpha if method != "ratio" else None,
        beta=beta if method != "ratio" else None,
        reference_taiex=ref_taiex,
        reference_etf=ref_etf,
    )


def tx_to_etf(
    tx_price: float,
    df: pd.DataFrame,
    etf_name: str = "0050反",
    method: Method = "spread",
    basis: float = 0.0,
) -> ConversionResult:
    implied_taiex = tx_price - basis
    result = taiex_to_etf(implied_taiex, df, etf_name=etf_name, method=method)
    return ConversionResult(
        taiex=implied_taiex,
        implied_etf=result.implied_etf,
        etf_name=etf_name,
        method=result.method,
        ratio=result.ratio,
        alpha=result.alpha,
        beta=result.beta,
        reference_taiex=result.reference_taiex,
        reference_etf=result.reference_etf,
    )


# 向後相容別名
taiex_to_0050反 = lambda taiex, df, method="spread": taiex_to_etf(taiex, df, "0050反", method)


def _scenarios(df: pd.DataFrame, etf_name: str, method: Method) -> list[tuple[str, float, float]]:
    ref_taiex = float(df.iloc[-1]["taiex"])
    rows: list[tuple[str, float, float]] = []
    for pct in (-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03):
        t = ref_taiex * (1 + pct)
        p = taiex_to_etf(t, df, etf_name, method).implied_etf
        label = f"{pct * 100:+.0f}%" if pct != 0 else "基準"
        rows.append((label, t, p))
    return rows


def render_html(
    df: pd.DataFrame,
    results: dict[str, ConversionResult],
    *,
    input_price: float,
    is_tx: bool = False,
    basis: float = 0.0,
    method: Method = "spread",
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    latest = df.iloc[-1]
    input_label = "台指期" if is_tx else "TAIEX"
    implied_label = (
        f"台指期 {input_price:,.0f}（基差 {basis:,.0f}）→ 隱含 TAIEX {list(results.values())[0].taiex:,.2f}"
        if is_tx
        else f"TAIEX {input_price:,.2f}"
    )
    method_desc = {
        "spread": "價差法：ETF = 參考 ETF + β × (TAIEX − 參考 TAIEX)",
        "ratio": "倍率法：ETF = TAIEX × (最新 ETF / 最新 TAIEX)",
        "regression": "迴歸法：ETF = α + β × TAIEX",
    }[method]

    product_cards = ""
    for name in ETF_PRODUCTS:
        col = _etf_column(name)
        r = results[name]
        product_cards += f"""
      <div class="card result">
        <div class="label">推算 {name}</div>
        <div class="value">{r.implied_etf:.2f}</div>
      </div>"""

    live_cards = f"""
      <div class="card">
        <div class="label">最新 TAIEX</div>
        <div class="value">{latest['taiex']:,.2f}</div>
      </div>
      <div class="card">
        <div class="label">最新 0050</div>
        <div class="value">{latest['etf_0050']:.2f}</div>
      </div>
      <div class="card">
        <div class="label">最新 0050反</div>
        <div class="value">{latest['etf_0050_inv']:.2f}</div>
      </div>
      <div class="card highlight">
        <div class="label">輸入 {input_label}</div>
        <div class="value">{input_price:,.2f}</div>
      </div>"""

    sections = ""
    for name in ETF_PRODUCTS:
        r = results[name]
        alpha, beta = fit_regression(df, name)
        ratio = current_ratio(df, name)
        scenarios = _scenarios(df, name, method)
        scenario_rows = "\n".join(
            f"<tr><td>{lbl}</td><td class='num'>{t:,.2f}</td><td class='num'>{p:.2f}</td></tr>"
            for lbl, t, p in scenarios
        )
        grid_rows = "\n".join(
            f"<tr><td class='num'>{t:,.2f}</td><td class='num'>{p:.2f}</td></tr>"
            for t, p in [
                (ref * f, taiex_to_etf(ref * f, df, name, method).implied_etf)
                for ref in [float(r.reference_taiex or latest["taiex"])]
                for f in (0.90, 0.95, 1.0, 1.05, 1.10)
            ]
        )
        sections += f"""
    <section>
      <h2>{name} 換算結果</h2>
      <table>
        <tr><th>項目</th><th class="num">數值</th></tr>
        <tr><td>推算 {name}</td><td class="num">{r.implied_etf:.2f}</td></tr>
        <tr><td>參考 TAIEX</td><td class="num">{r.reference_taiex:,.2f}</td></tr>
        <tr><td>參考 {name}</td><td class="num">{r.reference_etf:.2f}</td></tr>
        <tr><td>倍率 ({name}/TAIEX)</td><td class="num">{ratio:.6f}</td></tr>
        <tr><td>α</td><td class="num">{alpha:.4f}</td></tr>
        <tr><td>β</td><td class="num">{beta:.6f}</td></tr>
      </table>
      <h3>TAIEX 情境</h3>
      <table>
        <tr><th>變動</th><th class="num">TAIEX</th><th class="num">推算 {name}</th></tr>
        {scenario_rows}
      </table>
      <h3>價位對照</h3>
      <table>
        <tr><th class="num">TAIEX</th><th class="num">推算 {name}</th></tr>
        {grid_rows}
      </table>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TAIEX → 0050 / 0050反 換算</title>
  <style>
    :root {{ --bg:#0f1419; --card:#1a2332; --border:#2d3a4f; --text:#e7ecf3; --muted:#8b9cb3; --accent:#3d8bfd; --green:#3dd68c; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:"Segoe UI","Microsoft JhengHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.5; padding:24px; }}
    .wrap {{ max-width:960px; margin:0 auto; }}
    h1 {{ font-size:1.5rem; margin:0 0 8px; }}
    h3 {{ font-size:0.95rem; color:var(--muted); margin:16px 0 8px; }}
    .sub {{ color:var(--muted); font-size:0.9rem; margin-bottom:24px; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; margin-bottom:20px; }}
    .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }}
    .card .label {{ color:var(--muted); font-size:0.85rem; }}
    .card .value {{ font-size:1.45rem; font-weight:600; margin-top:4px; }}
    .card.highlight .value {{ color:var(--accent); }}
    .card.result .value {{ color:var(--green); }}
    section {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; margin-bottom:16px; }}
    section h2 {{ font-size:1rem; margin:0 0 12px; color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; font-size:0.95rem; }}
    th,td {{ padding:8px 10px; border-bottom:1px solid var(--border); }}
    th {{ color:var(--muted); font-weight:500; text-align:left; }}
    td.num,th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .formula {{ font-family:Consolas,monospace; color:var(--accent); font-size:0.9rem; }}
    .meta {{ color:var(--muted); font-size:0.85rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>TAIEX / 台指期 → 0050 / 0050反 換算</h1>
    <p class="sub">產生時間：{generated_at.strftime("%Y-%m-%d %H:%M:%S")}　｜　樣本 {df.index[0].date()} ~ {df.index[-1].date()}（{len(df)} 日）</p>
    <div class="cards">{live_cards}{product_cards}</div>
    <section>
      <h2>換算說明</h2>
      <p>{implied_label}</p>
      <p class="formula">{method_desc}</p>
    </section>
    {sections}
    <p class="meta">資料來源：Yahoo Finance（^TWII、0050.TW、00632R.TW）。僅供參考，非投資建議。</p>
  </div>
</body>
</html>"""


def write_html_report(
    output_path: str,
    df: pd.DataFrame,
    results: dict[str, ConversionResult],
    **kwargs,
) -> str:
    html = render_html(df, results, **kwargs)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def format_result(result: ConversionResult, label: str = "TAIEX") -> str:
    name = result.etf_name
    lines = [
        f"{label}: {result.taiex:,.2f}",
        f"推算 {name}: {result.implied_etf:.2f} 元",
        f"方法: {result.method}",
    ]
    if result.reference_taiex is not None:
        lines.append(
            f"參考 TAIEX: {result.reference_taiex:,.2f} | 參考 {name}: {result.reference_etf:.2f}"
        )
    if result.ratio is not None:
        lines.append(f"倍率 ({name}/TAIEX): {result.ratio:.6f}")
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

    parser = argparse.ArgumentParser(description="TAIEX / 台指期 → 0050、0050反 價格換算")
    parser.add_argument("price", type=float, nargs="?", help="TAIEX 點位或台指期價格")
    parser.add_argument("--tx", action="store_true", help="輸入為台指期價格")
    parser.add_argument("--basis", type=float, default=0.0, help="期貨基差")
    parser.add_argument("--etf", choices=list(ETF_PRODUCTS), default=None, help="指定 ETF（預設顯示全部）")
    parser.add_argument("--method", choices=["ratio", "regression", "spread"], default="spread")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--html", metavar="FILE", help="輸出 HTML 報表")
    args = parser.parse_args()

    df = fetch_prices(lookback_days=args.days)
    latest = df.iloc[-1]
    price = args.price if args.price is not None else float(latest["taiex"])

    names = [args.etf] if args.etf else list(ETF_PRODUCTS)
    results = {
        name: (tx_to_etf if args.tx else taiex_to_etf)(
            price, df, etf_name=name, method=args.method, **({"basis": args.basis} if args.tx else {})
        )
        for name in names
    }

    if args.html:
        out = write_html_report(
            args.html, df, results,
            input_price=price, is_tx=args.tx, basis=args.basis, method=args.method,
        )
        print(f"HTML 已輸出：{out}")
        return

    print(
        f"最新 TAIEX: {latest['taiex']:,.2f} | "
        f"0050: {latest['etf_0050']:.2f} | 0050反: {latest['etf_0050_inv']:.2f}"
    )
    print(f"樣本期間: {df.index[0].date()} ~ {df.index[-1].date()} ({len(df)} 日)")
    print("-" * 50)

    label = f"台指期 {price:,.0f} (隱含 TAIEX)" if args.tx else "TAIEX"
    for i, name in enumerate(names):
        r = results[name]
        if i == 0:
            print(format_result(r, label=label))
        else:
            print(f"[{name}]")
            print(f"推算 {name}: {r.implied_etf:.2f} 元（方法: {r.method}）")
        print("-" * 50)


if __name__ == "__main__":
    main()
