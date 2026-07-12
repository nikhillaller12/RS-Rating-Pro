import io
import requests
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from .config import NSE_NIFTY500_URL, NSE_MICROCAP250_URL

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _fetch_history(yahoo_sym: str) -> pd.Series | None:
    """
    Fetch close price history for a Yahoo Finance symbol.

    Attempt order (handles intermittent yfinance/.NS rate-limit failures):
      1. period="18mo"
      2. period="2y"
      3. explicit start/end date range covering ~18 months

    Returns a named Series or None if all attempts fail.
    """
    from datetime import datetime, timedelta

    ticker = yf.Ticker(yahoo_sym)

    for period in ("18mo", "2y"):
        try:
            df = ticker.history(period=period, auto_adjust=True)
            if not df.empty:
                return df["Close"].rename(yahoo_sym)
        except Exception:
            pass

    # Final fallback: explicit date range
    try:
        end   = datetime.today()
        start = end - timedelta(days=548)   # ~18 months in calendar days
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
        )
        if not df.empty:
            return df["Close"].rename(yahoo_sym)
    except Exception:
        pass

    return None


# ── US — S&P 500 ─────────────────────────────────────────────────────────────

def symbols():
    """Download latest S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    table = pd.read_html(io.StringIO(resp.text))[0]
    syms = table["Symbol"].tolist()
    # Yahoo uses '-' instead of '.'
    return [s.replace(".", "-") for s in syms]


def fetch(symbol):
    try:
        s = _fetch_history(symbol)
        if s is None:
            print(f"Failed: {symbol} -> no data")
        return s
    except Exception as e:
        print(f"Failed: {symbol} -> {e}")
        return None


def download_all():
    syms = symbols()
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = executor.map(fetch, syms)
        for item in tqdm(futures, total=len(syms), desc="US (S&P 500)"):
            if item is not None:
                results.append(item)
    return pd.concat(results, axis=1)


# ── India — Nifty 750 (Nifty 500 + Microcap 250) ────────────────────────────

def symbols_india():
    """
    Download Nifty 750 constituents from NSE India.
    Returns a list of (yahoo_symbol, company, sector) tuples.
    NSE symbols need a '.NS' suffix for Yahoo Finance.
    """
    rows = []
    for url in [NSE_NIFTY500_URL, NSE_MICROCAP250_URL]:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        for _, row in df.iterrows():
            sym_nse = str(row["Symbol"]).strip()
            rows.append({
                "yahoo":    sym_nse + ".NS",
                "symbol":   sym_nse,
                "company":  str(row["Company Name"]).strip(),
                "industry": str(row["Industry"]).strip(),
                "sector":   "",   # NSE CSV has Industry, not GICS Sector
            })

    # De-duplicate (Nifty 500 and Microcap 250 can overlap at the boundary)
    seen = set()
    unique = []
    for r in rows:
        if r["yahoo"] not in seen:
            seen.add(r["yahoo"])
            unique.append(r)
    return unique


def fetch_india(meta_row):
    """Fetch close price history for one NSE ticker."""
    yahoo_sym = meta_row["yahoo"]
    try:
        s = _fetch_history(yahoo_sym)
        if s is None:
            print(f"Failed: {yahoo_sym} -> no data")
        return s
    except Exception as e:
        print(f"Failed: {yahoo_sym} -> {e}")
        return None


def download_all_india():
    """
    Returns (prices_df, meta_list).
    prices_df columns are Yahoo symbols (e.g. 'RELIANCE.NS').
    meta_list is the list of dicts from symbols_india().
    """
    meta = symbols_india()
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = executor.map(fetch_india, meta)
        for item in tqdm(futures, total=len(meta), desc="India (Nifty 750)"):
            if item is not None:
                results.append(item)
    prices = pd.concat(results, axis=1)
    return prices, meta
