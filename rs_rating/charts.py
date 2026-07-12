"""
charts.py — builds a 3-panel RS comparison chart for a given ticker.

Panels:
  1. Normalized price performance: ticker vs benchmark index (trailing 12M, rebased to 100)
  2. Period return bars: ticker 3M/6M/9M/12M vs benchmark median
  3. RS Rating gauge (1–99)

Supports both US (S&P 500 / SPY) and India (Nifty 750 / ^NSEI) markets.
"""

import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import CACHE, INDIA_CACHE, INDIA_BENCHMARK_TICKER


def chart(symbol: str, market: str = "us") -> go.Figure:
    """
    Build the RS comparison chart.

    Args:
        symbol: Ticker symbol.
                  US market  → e.g. 'AAPL'
                  India market → bare NSE symbol e.g. 'RELIANCE' or 'RELIANCE.NS'
        market: 'us' or 'india'
    """
    market = market.lower()

    # ── 1. Resolve symbols and pull lookup data ───────────────────────────────
    if market == "india":
        from .engine import lookup_india
        yahoo_sym      = symbol if symbol.upper().endswith(".NS") else symbol.upper() + ".NS"
        display_sym    = yahoo_sym.replace(".NS", "")
        bench_ticker   = INDIA_BENCHMARK_TICKER   # ^NSEI
        bench_label    = "Nifty 50"
        cache_path     = INDIA_CACHE
        r              = lookup_india(symbol)
    else:
        from .engine import lookup
        yahoo_sym      = symbol.upper()
        display_sym    = yahoo_sym
        bench_ticker   = "SPY"
        bench_label    = "SPY"
        cache_path     = CACHE
        r              = lookup(symbol)

    # ── 2. Price history: ticker + index (trailing 12M) ──────────────────────
    ticker_hist = yf.Ticker(yahoo_sym).history(period="12mo", auto_adjust=True)["Close"]
    index_hist  = yf.Ticker(bench_ticker).history(period="12mo", auto_adjust=True)["Close"]

    common  = ticker_hist.index.intersection(index_hist.index)
    t       = ticker_hist.loc[common]
    s       = index_hist.loc[common]
    t_norm  = t / t.iloc[0] * 100
    s_norm  = s / s.iloc[0] * 100

    # ── 3. Benchmark median returns ───────────────────────────────────────────
    bench = pd.read_parquet(cache_path)
    bench_medians = {
        "3M":  bench["Return_3m"].median(),
        "6M":  bench["Return_6m"].median(),
        "9M":  bench["Return_9m"].median(),
        "12M": bench["Return_12m"].median(),
    }
    ticker_returns = {
        "3M":  r["return_3m"],
        "6M":  r["return_6m"],
        "9M":  r["return_9m"],
        "12M": r["return_12m"],
    }

    periods      = list(ticker_returns.keys())
    t_vals       = [ticker_returns[p] * 100 for p in periods]
    b_vals       = [bench_medians[p]   * 100 for p in periods]
    bar_colors_t = ["#22c55e" if v >= 0 else "#ef4444" for v in t_vals]

    rs = r["rs"]

    # ── 4. Build figure ───────────────────────────────────────────────────────
    index_label = f"Nifty 750 Median" if market == "india" else "S&P 500 Median"

    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.45, 0.30, 0.25],
        subplot_titles=(
            f"Price Performance vs {bench_label} — trailing 12M (rebased to 100)",
            f"Period Returns: {display_sym} vs {index_label}",
            f"RS Rating: {rs} / 99",
        ),
        vertical_spacing=0.10,
    )

    # Panel 1 — price lines
    dates = [str(d)[:10] for d in common]
    fig.add_trace(go.Scatter(
        x=dates, y=t_norm.values,
        name=display_sym,
        line=dict(color="#3b82f6", width=2),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=s_norm.values,
        name=bench_label,
        line=dict(color="#94a3b8", width=1.5, dash="dot"),
    ), row=1, col=1)
    fig.add_hline(y=100, line=dict(color="#d1d5db", width=1, dash="dash"), row=1, col=1)

    # Panel 2 — grouped return bars
    fig.add_trace(go.Bar(
        x=periods, y=b_vals,
        name=index_label,
        marker_color="#94a3b8",
        opacity=0.7,
        offsetgroup=0,
    ), row=2, col=1)
    fig.add_trace(go.Bar(
        x=periods, y=t_vals,
        name=display_sym,
        marker_color=bar_colors_t,
        offsetgroup=1,
    ), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="#6b7280", width=1), row=2, col=1)

    # Panel 3 — RS gauge
    fig.add_trace(go.Bar(
        x=[99], y=["RS"], orientation="h",
        marker_color="#e5e7eb", width=0.4,
        showlegend=False, opacity=0.4,
    ), row=3, col=1)
    fig.add_trace(go.Bar(
        x=[rs], y=["RS"], orientation="h",
        marker=dict(
            color=rs,
            colorscale=[[0.0, "#ef4444"], [0.5, "#f59e0b"], [1.0, "#22c55e"]],
            cmin=1, cmax=99, showscale=False,
        ),
        width=0.4, showlegend=False,
        text=f"  RS {rs}",
        textposition="outside",
        textfont=dict(size=16, color="#1f2328"),
    ), row=3, col=1)

    # ── 5. Layout ─────────────────────────────────────────────────────────────
    company  = r.get("company", display_sym)
    sector   = r.get("sector", "") or r.get("industry", "")
    pct      = r["percentile"]
    rank     = r["rank"]
    total    = r["total"]
    score_v  = r["score"]
    mkt_label = "🇮🇳 Nifty 750" if market == "india" else "🇺🇸 S&P 500"

    title_text = (
        f"<b>{display_sym}</b>  ·  {company}"
        + (f"  ·  {sector}" if sector else "")
        + f"  ·  {mkt_label}"
        + f"<br><sup>Rank {rank}/{total}  ·  {pct:.1f}th percentile  "
        + f"·  Weighted Score {score_v:.4f}</sup>"
    )

    fig.update_layout(
        title=dict(text=title_text, x=0.01, font=dict(size=15)),
        height=720,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f7f8fa",
        font=dict(family="-apple-system, 'Segoe UI', sans-serif", size=12, color="#1f2328"),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
        barmode="overlay",
        margin=dict(l=60, r=40, t=90, b=40),
    )

    fig.update_yaxes(gridcolor="#e5e7eb", row=1, col=1)
    fig.update_yaxes(gridcolor="#e5e7eb", ticksuffix="%", row=2, col=1)
    fig.update_xaxes(range=[0, 99], row=3, col=1, showticklabels=False)
    fig.update_yaxes(showticklabels=False, row=3, col=1)

    for p, tv in zip(periods, t_vals):
        fig.add_annotation(
            x=p, y=tv + (1 if tv >= 0 else -1),
            text=f"{tv:+.1f}%",
            showarrow=False,
            font=dict(size=10, color="#1f2328"),
            yref="y2",
        )

    return fig


def open_chart(symbol: str, market: str = "us") -> None:
    """Render the chart and open it in the default browser."""
    chart(symbol, market=market).show()
