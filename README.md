# RS Rating Pro

Relative Strength Rating engine for **S&P 500 (US)** and **Nifty 750 (India)** stocks.  
Scores every stock using IBD-style non-overlapping quarterly momentum, ranks it against
its market benchmark, and surfaces the result as a CLI report, an interactive Plotly
chart, a Streamlit dashboard, and a FastAPI endpoint.

---

## Requirements

| Dependency | Version pinned |
|---|---|
| Python | ≥ 3.10 (3.12 recommended) |
| pandas | 3.x |
| numpy | 2.x |
| yfinance | 1.5.x |
| plotly | ≥ 5.0, < 6.0 |
| streamlit | ≥ 1.38, < 1.42 |
| fastapi + uvicorn | 0.13x / 0.5x |
| tqdm | 4.x |
| pyarrow | 25.x |
| requests | 2.x |
| lxml | 6.x |

All pinned automatically via `pip install -e .`

---

## Setup (new machine)

```bash
# 0. macOS — install Python 3.12 if not already present
brew install python@3.12

# 1. Clone the repository
git clone <repo-url>
cd RS-Rating-Pro

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install the package and all dependencies
pip install -e .

# 4a. Build the US benchmark (S&P 500)
#     Downloads ~18 months of price history for ~503 stocks — takes ~15–30 s
python -m rs_rating.cli --update

# 4b. Build the India benchmark (Nifty 750 = Nifty 500 + Microcap 250)
#     Downloads ~18 months of price history for ~750 NSE stocks — takes ~30–60 s
python -m rs_rating.cli --update --market india
```

---

## CLI Usage

### US market (S&P 500) — default

```bash
# Text report
python -m rs_rating.cli AAPL
python -m rs_rating.cli PLTR
python -m rs_rating.cli NVDA

# Interactive 3-panel chart (opens in browser)
python -m rs_rating.cli AAPL --chart
python -m rs_rating.cli NVDA --chart
```

### India market (Nifty 750)

```bash
# Text report — use bare NSE symbol
python -m rs_rating.cli RELIANCE --market india
python -m rs_rating.cli TCS      --market india
python -m rs_rating.cli HDFCBANK --market india
python -m rs_rating.cli INFY     --market india

# Interactive chart — ticker vs Nifty 50
python -m rs_rating.cli RELIANCE --market india --chart
python -m rs_rating.cli TCS      --market india --chart

# Stocks outside Nifty 750 also work (scored against the Nifty 750 benchmark)
python -m rs_rating.cli IDEAFORGE  --market india
python -m rs_rating.cli GLOBUSSPR  --market india
python -m rs_rating.cli EASEMYTRIP --market india
python -m rs_rating.cli LANDMARK   --market india
python -m rs_rating.cli AEROFLEX   --market india
```

### Refresh benchmarks (run daily for fresh data)

```bash
python -m rs_rating.cli --update                   # refresh US
python -m rs_rating.cli --update --market india    # refresh India
```

---

## Streamlit Dashboard

```bash
streamlit run dashboard/app.py
```

Open http://localhost:8501 in your browser.

The dashboard has two tabs:
- **🇺🇸 S&P 500** — look up any US ticker, compare vs SPY and S&P 500 median
- **🇮🇳 Nifty 750** — look up any NSE ticker, compare vs Nifty 50 and Nifty 750 median

Each tab shows:
- RS Rating, Percentile, Rank, Weighted Score, 3M Return
- Period returns table vs benchmark median (▲/▼ vs median)
- 3-panel interactive Plotly chart
- Top 10 / Bottom 10 stocks by RS
- Full benchmark table (expandable)

---

## FastAPI Server

```bash
uvicorn rs_rating.api:app --reload
```

Open http://localhost:8000 → redirects to interactive Swagger docs at `/docs`.

### US endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/` | Redirects to `/docs` |
| GET | `/stock/{ticker}` | RS report for any US ticker (e.g. `AAPL`, `NVDA`) |
| GET | `/benchmark` | Full S&P 500 ranked table |
| GET | `/top?n=20` | Top N stocks by RS |
| GET | `/bottom?n=20` | Bottom N stocks by RS |
| GET | `/sector/{sector}` | All stocks in a GICS sector (e.g. `Information Technology`) |

### India endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/india/stock/{ticker}` | RS report for any NSE ticker — accepts `RELIANCE` or `RELIANCE.NS` |
| GET | `/india/benchmark` | Full Nifty 750 ranked table |
| GET | `/india/top?n=20` | Top N India stocks by RS |
| GET | `/india/bottom?n=20` | Bottom N India stocks by RS |
| GET | `/india/industry/{industry}` | All stocks in an NSE industry (e.g. `Healthcare`) |

#### Example API calls

```bash
# US
curl http://localhost:8000/stock/AAPL
curl http://localhost:8000/top?n=10
curl "http://localhost:8000/sector/Information%20Technology"

# India
curl http://localhost:8000/india/stock/RELIANCE
curl http://localhost:8000/india/stock/RELIANCE.NS   # Yahoo form also accepted
curl http://localhost:8000/india/top?n=10
curl http://localhost:8000/india/industry/Healthcare

# Stocks outside Nifty 750 (scored against the benchmark)
curl http://localhost:8000/india/stock/IDEAFORGE
curl http://localhost:8000/india/stock/GLOBUSSPR
curl http://localhost:8000/india/stock/EASEMYTRIP
```

---

## How the RS Rating works

1. **Download** closing prices (~18 months) for all constituents via yfinance.
2. **Score** each stock using **non-overlapping** quarterly returns (IBD-style):
   - Q4 — most recent 3M × **0.40**
   - Q3 — prior 3M       × **0.20**
   - Q2 — prior 3M       × **0.20**
   - Q1 — oldest 3M      × **0.20**
3. **Rank** all stocks by weighted score, assign Rank / Percentile / RS (1–99).
4. **Store** the full benchmark in a parquet file:
   `Ticker, Company, Sector, Industry, Return_3m/6m/9m/12m, WeightedScore, Rank, Percentile, RS`
5. **Lookup** any ticker by computing the same score and inserting it into the
   sorted benchmark via binary search — works for stocks outside the index too.

### Price fetch resilience

yfinance occasionally fails to return data for `.NS` tickers with a period string.
`_fetch_history()` retries automatically in this order:
1. `period="18mo"`
2. `period="2y"` (fallback)
3. Explicit `start`/`end` date range covering ~18 months (final fallback)

---

## Data sources

| Market | Constituent list | Price data | Chart benchmark |
|---|---|---|---|
| US | Wikipedia — List of S&P 500 companies | Yahoo Finance (yfinance) | SPY |
| India | NSE India CSV (`ind_nifty500list.csv` + `ind_niftymicrocap250_list.csv`) | Yahoo Finance `.NS` suffix | `^NSEI` (Nifty 50) |

---

## File structure

```
RS-Rating-Pro/
├── rs_rating/
│   ├── config.py       # Lookback periods, weights, cache paths, NSE URLs
│   ├── downloader.py   # Symbol lists + price fetching (US & India)
│   ├── momentum.py     # Non-overlapping quarterly RS scoring
│   ├── engine.py       # update() / lookup() for US and India
│   ├── charts.py       # 3-panel Plotly chart (market-aware)
│   ├── cli.py          # CLI entry point (--update, --chart, --market)
│   └── api.py          # FastAPI routes (/stock, /india/stock, etc.)
├── dashboard/
│   └── app.py          # Streamlit dashboard (US + India tabs)
├── data/
│   ├── benchmark.parquet        # S&P 500 ranked benchmark
│   └── india_benchmark.parquet  # Nifty 750 ranked benchmark
└── pyproject.toml
```
