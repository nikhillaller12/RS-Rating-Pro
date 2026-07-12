import pandas as pd
import streamlit as st

from rs_rating.engine import lookup, lookup_india
from rs_rating.charts import chart
from rs_rating.config import CACHE, INDIA_CACHE

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="RS Rating Pro", page_icon="📈", layout="wide")
st.title("📈 RS Rating Pro")
st.caption("Relative Strength ratings — S&P 500 (US) and Nifty 750 (India)")

# ── Market selector ───────────────────────────────────────────────────────────
market_tab_us, market_tab_india = st.tabs(["🇺🇸  S&P 500", "🇮🇳  Nifty 750"])


# ─────────────────────────────────────────────────────────────────────────────
def _render_market(market: str, cache_path: str, bench_name: str,
                   default_ticker: str, lookup_fn):
    """Shared rendering logic for both markets."""

    # ── Sidebar-style columns: input left, benchmark stats right ─────────────
    col_input, col_stats = st.columns([1, 3])

    with col_input:
        ticker  = st.text_input("Ticker symbol", value=default_ticker,
                                key=f"ticker_{market}").strip().upper()
        analyze = st.button("Analyze", type="primary",
                            use_container_width=True, key=f"btn_{market}")
        if market == "india":
            st.caption("Enter NSE symbol, e.g. RELIANCE, TCS, INFY")
        else:
            st.caption("Enter NYSE/NASDAQ symbol, e.g. AAPL, NVDA, MSFT")

        # Benchmark summary
        try:
            bench = pd.read_parquet(cache_path)
            st.divider()
            st.metric("Stocks in benchmark", len(bench))
            st.metric("Top RS ticker",    bench.loc[bench["RS"].idxmax(), "Ticker"].replace(".NS", ""))
            st.metric("Lowest RS ticker", bench.loc[bench["RS"].idxmin(), "Ticker"].replace(".NS", ""))
        except FileNotFoundError:
            cmd = f"python -m rs_rating.cli --update" + (" --market india" if market == "india" else "")
            st.warning(f"No benchmark yet.\n\nRun:\n```\n{cmd}\n```")

    with col_stats:
        if analyze and ticker:
            with st.spinner(f"Fetching {ticker}…"):
                try:
                    r = lookup_fn(ticker)
                except Exception as e:
                    st.error(f"Could not compute RS for **{ticker}**: {e}")
                    st.stop()

            # ── Metric row ────────────────────────────────────────────────────
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("RS Rating",  r["rs"])
            m2.metric("Percentile", f"{r['percentile']:.1f}%")
            m3.metric("Rank (Top)",  f"#{r['rank_from_top']} of {r['total']}")
            m4.metric("Wtd Score",  f"{r['score']:.4f}")
            m5.metric("3M Return",  f"{r['return_3m']:+.1%}")

            # Company / sector
            parts = [p for p in [r.get("company"), r.get("sector") or r.get("industry")] if p]
            if parts:
                st.markdown("  ·  ".join(f"**{p}**" for p in parts))

            st.divider()

            # ── Period returns ────────────────────────────────────────────────
            st.subheader("Period Returns")
            try:
                bench = pd.read_parquet(cache_path)
                medians = {p: bench[f"Return_{p.lower()}"].median()
                           for p in ["3m", "6m", "9m", "12m"]}
                ret_df = pd.DataFrame({
                    "Period": ["3M", "6M", "9M", "12M"],
                    ticker: [f"{r[f'return_{p}']:+.2%}" for p in ["3m","6m","9m","12m"]],
                    f"{bench_name} Median": [f"{medians[p]:+.2%}" for p in ["3m","6m","9m","12m"]],
                    "vs Benchmark": [
                        f"{'▲' if r[f'return_{p}'] >= medians[p] else '▼'} {abs(r[f'return_{p}'] - medians[p]):.2%}"
                        for p in ["3m","6m","9m","12m"]
                    ],
                })
            except Exception:
                ret_df = pd.DataFrame({
                    "Period": ["3M", "6M", "9M", "12M"],
                    ticker: [f"{r[f'return_{p}']:+.2%}" for p in ["3m","6m","9m","12m"]],
                })
            st.dataframe(ret_df, hide_index=True, use_container_width=True)

            st.divider()

            # ── Chart ─────────────────────────────────────────────────────────
            st.subheader("Comparison Chart")
            try:
                fig = chart(ticker, market=market)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Chart error: {e}")

            st.divider()

            # ── Top / Bottom 10 ───────────────────────────────────────────────
            try:
                bench = pd.read_parquet(cache_path)
                disp_cols = ["Ticker", "Company", "Industry", "RS", "Percentile",
                             "Return_3m", "Return_6m", "Return_9m", "Return_12m"]
                if "Sector" in bench.columns:
                    disp_cols.insert(3, "Sector")
                disp_cols = [c for c in disp_cols if c in bench.columns]

                ca, cb = st.columns(2)
                for col_widget, label, fn in [
                    (ca, f"🏆 Top 10  {bench_name}", lambda df: df.nlargest(10, "RS")),
                    (cb, f"📉 Bottom 10  {bench_name}", lambda df: df.nsmallest(10, "RS")),
                ]:
                    with col_widget:
                        st.subheader(label)
                        sub = fn(bench)[disp_cols].copy()
                        sub["Ticker"] = sub["Ticker"].str.replace(".NS", "", regex=False)
                        for c in ["Return_3m", "Return_6m", "Return_9m", "Return_12m"]:
                            if c in sub.columns:
                                sub[c] = sub[c].map("{:+.1%}".format)
                        st.dataframe(sub, hide_index=True, use_container_width=True)
            except Exception:
                pass
        else:
            st.info(f"Enter a **{bench_name}** ticker and click **Analyze**.")

    # ── Full benchmark table (always shown below) ─────────────────────────────
    try:
        bench = pd.read_parquet(cache_path)
        with st.expander(f"📊 Full {bench_name} Benchmark ({len(bench)} stocks)", expanded=False):
            disp = bench.copy()
            disp["Ticker"] = disp["Ticker"].str.replace(".NS", "", regex=False)
            for c in ["Return_3m", "Return_6m", "Return_9m", "Return_12m"]:
                if c in disp.columns:
                    disp[c] = disp[c].map("{:+.1%}".format)
            if "WeightedScore" in disp.columns:
                disp["WeightedScore"] = disp["WeightedScore"].map("{:.4f}".format)
            st.dataframe(
                disp.sort_values("RS", ascending=False),
                hide_index=True, use_container_width=True, height=500,
            )
    except FileNotFoundError:
        pass


# ── Render each tab ───────────────────────────────────────────────────────────
with market_tab_us:
    _render_market(
        market="us",
        cache_path=CACHE,
        bench_name="S&P 500",
        default_ticker="AAPL",
        lookup_fn=lookup,
    )

with market_tab_india:
    _render_market(
        market="india",
        cache_path=INDIA_CACHE,
        bench_name="Nifty 750",
        default_ticker="RELIANCE",
        lookup_fn=lookup_india,
    )
