
# Trading-day lookbacks for each non-overlapping quarter
# Q4 = most recent 3M, Q3 = prior 3M, Q2 = prior 3M, Q1 = oldest 3M
LOOKBACKS = {
    "3m":  (0,   63),   # Q4: today  → 63 td ago
    "6m":  (63,  126),  # Q3: 63 td  → 126 td ago
    "9m":  (126, 189),  # Q2: 126 td → 189 td ago
    "12m": (189, 252),  # Q1: 189 td → 252 td ago
}

# IBD-style weighting: most recent quarter counts double
WEIGHTS = {"3m": 0.4, "6m": 0.2, "9m": 0.2, "12m": 0.2}

# ── Cache paths ───────────────────────────────────────────────────────────────
CACHE       = "data/benchmark.parquet"        # S&P 500 (US)
INDIA_CACHE = "data/india_benchmark.parquet"  # Nifty 750 (India)

# ── NSE constituent CSV URLs ──────────────────────────────────────────────────
NSE_NIFTY500_URL     = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
NSE_MICROCAP250_URL  = "https://archives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv"

# Benchmark index ticker used as the comparison line in India charts
INDIA_BENCHMARK_TICKER = "^NSEI"   # Nifty 50 index on Yahoo Finance
