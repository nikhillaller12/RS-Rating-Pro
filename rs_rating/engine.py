import io
import bisect

import requests
import pandas as pd

from .downloader import download_all, download_all_india, _fetch_history
from .momentum import score
from .config import CACHE, INDIA_CACHE

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; rs-rating-pro/1.0; "
        "+https://github.com/your-repo)"
    )
}


# ── US helpers ────────────────────────────────────────────────────────────────

def _sp500_meta():
    """Return a dict of {symbol: {company, sector, industry}} from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    table = pd.read_html(io.StringIO(resp.text))[0]
    meta = {}
    for _, row in table.iterrows():
        sym = row["Symbol"].replace(".", "-")
        meta[sym] = {
            "company":  row["Security"],
            "sector":   row["GICS Sector"],
            "industry": row["GICS Sub-Industry"],
        }
    return meta


def _build_benchmark(rows, cache_path):
    """Sort by WeightedScore, assign Rank / Percentile / RS, save parquet."""
    df = pd.DataFrame(rows).sort_values("WeightedScore").reset_index(drop=True)
    n  = len(df)
    # Rank ascending from weakest (used for percentile calculation)
    df["Rank"]          = df.index + 1
    # Rank descending from strongest — Rank_From_Top=1 means best RS
    df["Rank_From_Top"] = n - df.index
    df["Percentile"]    = (df["Rank"] / n * 100).round(2)
    df["RS"]            = df["Percentile"].apply(lambda p: max(1, min(99, round(p * 0.99))))
    df.to_parquet(cache_path, index=False)
    return df


def _lookup_in_bench(bench, ticker, yahoo_sym, sc, cumulative):
    """Binary-search sc into a sorted benchmark and return the result dict."""
    arr   = bench["WeightedScore"].tolist()
    pos   = bisect.bisect_left(arr, sc)   # 0-based position from weakest end
    n     = len(arr) + 1                  # universe size including this ticker
    pct   = round(100 * pos / n, 2)
    rs    = max(1, min(99, round(pct * 0.99)))

    # rank_from_top: 1 = strongest, n = weakest
    rank_from_top = n - pos

    match    = bench[bench["Ticker"] == ticker]
    company  = match["Company"].iloc[0]  if len(match) else ""
    sector   = match["Sector"].iloc[0]   if len(match) else ""
    industry = match["Industry"].iloc[0] if len(match) else ""

    return {
        "ticker":         ticker,
        "company":        company,
        "sector":         sector,
        "industry":       industry,
        "return_3m":      cumulative["3m"],
        "return_6m":      cumulative["6m"],
        "return_9m":      cumulative["9m"],
        "return_12m":     cumulative["12m"],
        "score":          sc,
        "rank_from_top":  rank_from_top,   # 1 = best RS in universe
        "rank":           pos,             # kept for backward compat (0 = weakest)
        "total":          len(arr),
        "percentile":     pct,
        "rs":             rs,
    }


# ── US — S&P 500 ─────────────────────────────────────────────────────────────

def update():
    prices = download_all()
    meta   = _sp500_meta()

    rows = []
    for ticker in prices.columns:
        try:
            sc, cumulative = score(prices[ticker])
            info = meta.get(ticker, {"company": "", "sector": "", "industry": ""})
            rows.append({
                "Ticker":        ticker,
                "Company":       info["company"],
                "Sector":        info["sector"],
                "Industry":      info["industry"],
                "Return_3m":     cumulative["3m"],
                "Return_6m":     cumulative["6m"],
                "Return_9m":     cumulative["9m"],
                "Return_12m":    cumulative["12m"],
                "WeightedScore": sc,
            })
        except Exception:
            pass

    return _build_benchmark(rows, CACHE)


def lookup(symbol):
    bench = pd.read_parquet(CACHE)
    hist  = _fetch_history(symbol)
    if hist is None:
        raise ValueError(f"No price data available for {symbol}")
    sc, cumulative = score(hist)
    return _lookup_in_bench(bench, symbol, symbol, sc, cumulative)


# ── India — Nifty 750 ────────────────────────────────────────────────────────

def update_india():
    prices, meta_list = download_all_india()

    # Build a lookup dict from yahoo symbol → meta
    meta_dict = {m["yahoo"]: m for m in meta_list}

    rows = []
    for yahoo_sym in prices.columns:
        try:
            sc, cumulative = score(prices[yahoo_sym])
            info = meta_dict.get(yahoo_sym, {
                "symbol": yahoo_sym, "company": "", "industry": "", "sector": ""
            })
            rows.append({
                "Ticker":        yahoo_sym,          # e.g. RELIANCE.NS
                "NSE_Symbol":    info.get("symbol", yahoo_sym.replace(".NS", "")),
                "Company":       info.get("company", ""),
                "Sector":        info.get("sector", ""),
                "Industry":      info.get("industry", ""),
                "Return_3m":     cumulative["3m"],
                "Return_6m":     cumulative["6m"],
                "Return_9m":     cumulative["9m"],
                "Return_12m":    cumulative["12m"],
                "WeightedScore": sc,
            })
        except Exception:
            pass

    return _build_benchmark(rows, INDIA_CACHE)


def lookup_india(symbol):
    """
    Look up any NSE ticker.
    Accepts both bare NSE symbol (e.g. 'RELIANCE') and Yahoo form ('RELIANCE.NS').
    """
    bench = pd.read_parquet(INDIA_CACHE)

    # Normalise to Yahoo form
    yahoo_sym = symbol if symbol.endswith(".NS") else symbol + ".NS"
    nse_sym   = yahoo_sym.replace(".NS", "")

    hist = _fetch_history(yahoo_sym)
    if hist is None:
        raise ValueError(f"No price data available for {yahoo_sym}. "
                         f"Verify the NSE symbol is correct and listed on Yahoo Finance.")
    sc, cumulative = score(hist)

    # Match by Ticker column (which stores yahoo_sym)
    arr           = bench["WeightedScore"].tolist()
    pos           = bisect.bisect_left(arr, sc)
    n             = len(arr) + 1
    pct           = round(100 * pos / n, 2)
    rs            = max(1, min(99, round(pct * 0.99)))
    rank_from_top = n - pos   # 1 = strongest

    match    = bench[bench["Ticker"] == yahoo_sym]
    company  = match["Company"].iloc[0]  if len(match) else ""
    sector   = match["Sector"].iloc[0]   if len(match) else ""
    industry = match["Industry"].iloc[0] if len(match) else ""

    return {
        "ticker":        nse_sym,
        "yahoo":         yahoo_sym,
        "company":       company,
        "sector":        sector,
        "industry":      industry,
        "return_3m":     cumulative["3m"],
        "return_6m":     cumulative["6m"],
        "return_9m":     cumulative["9m"],
        "return_12m":    cumulative["12m"],
        "score":         sc,
        "rank_from_top": rank_from_top,
        "rank":          pos,
        "total":         len(arr),
        "percentile":    pct,
        "rs":            rs,
        "currency":      "INR",
    }
