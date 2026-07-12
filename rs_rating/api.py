import json
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse

from .engine import lookup, lookup_india
from .charts import chart
from .config import CACHE, INDIA_CACHE

app = FastAPI(
    title="RS Rating Pro",
    description=(
        "Relative Strength ratings — S&P 500 (US) and Nifty 750 (India). "
        "All India tickers accept bare NSE symbol (e.g. RELIANCE) or Yahoo form (RELIANCE.NS)."
    ),
    version="0.4.0",
    docs_url="/api-docs",
    redoc_url="/redoc",
)


# ── UI ────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui():
    """Interactive RS Rating dashboard."""
    return HTMLResponse(_UI_HTML)


# ── Chart endpoint (returns Plotly figure JSON) ───────────────────────────────

@app.get("/chart/{ticker}", summary="📈 Plotly chart JSON for a US ticker")
def chart_us(ticker: str):
    """Returns the Plotly figure as JSON so clients can render it."""
    try:
        fig = chart(ticker.upper(), market="us")
        return json.loads(fig.to_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/india/chart/{ticker}", summary="📈 Plotly chart JSON for an NSE ticker")
def chart_india(ticker: str):
    """Returns the Plotly figure as JSON so clients can render it."""
    try:
        fig = chart(ticker, market="india")
        return json.loads(fig.to_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── US — S&P 500 ─────────────────────────────────────────────────────────────

@app.get("/stock/{ticker}", summary="🇺🇸 RS Rating for a US ticker (S&P 500 benchmark)")
def stock(ticker: str):
    """RS rating for any US-listed ticker against the S&P 500 benchmark."""
    try:
        return lookup(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/benchmark", summary="🇺🇸 Full S&P 500 benchmark table")
def benchmark():
    try:
        return pd.read_parquet(CACHE).to_dict(orient="records")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run: python -m rs_rating.cli --update")


@app.get("/top", summary="🇺🇸 Top N US stocks by RS Rating")
def top(n: int = 20):
    try:
        return pd.read_parquet(CACHE).nlargest(n, "RS").to_dict(orient="records")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run: python -m rs_rating.cli --update")


@app.get("/bottom", summary="🇺🇸 Bottom N US stocks by RS Rating")
def bottom(n: int = 20):
    try:
        return pd.read_parquet(CACHE).nsmallest(n, "RS").to_dict(orient="records")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run: python -m rs_rating.cli --update")


@app.get("/sector/{sector}", summary="🇺🇸 US stocks in a GICS sector")
def by_sector(sector: str):
    try:
        df = pd.read_parquet(CACHE)
        result = df[df["Sector"].str.lower() == sector.lower()].sort_values("RS", ascending=False)
        if result.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Sector not found. Available: {sorted(df['Sector'].unique().tolist())}",
            )
        return result.to_dict(orient="records")
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run: python -m rs_rating.cli --update")


# ── India — Nifty 750 ────────────────────────────────────────────────────────

@app.get("/india/stock/{ticker}", summary="🇮🇳 RS Rating for an NSE ticker (Nifty 750 benchmark)")
def india_stock(ticker: str):
    """
    RS rating for any NSE-listed ticker against the Nifty 750 benchmark.
    Accepts bare NSE symbol (e.g. `RELIANCE`) or Yahoo form (`RELIANCE.NS`).
    """
    try:
        return lookup_india(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/india/benchmark", summary="🇮🇳 Full Nifty 750 benchmark table")
def india_benchmark():
    try:
        return pd.read_parquet(INDIA_CACHE).to_dict(orient="records")
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Run: python -m rs_rating.cli --update --market india",
        )


@app.get("/india/top", summary="🇮🇳 Top N India stocks by RS Rating")
def india_top(n: int = 20):
    try:
        return pd.read_parquet(INDIA_CACHE).nlargest(n, "RS").to_dict(orient="records")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run --update --market india first.")


@app.get("/india/bottom", summary="🇮🇳 Bottom N India stocks by RS Rating")
def india_bottom(n: int = 20):
    try:
        return pd.read_parquet(INDIA_CACHE).nsmallest(n, "RS").to_dict(orient="records")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run --update --market india first.")


@app.get("/india/industry/{industry}", summary="🇮🇳 India stocks in an NSE industry")
def india_by_industry(industry: str):
    try:
        df = pd.read_parquet(INDIA_CACHE)
        result = df[df["Industry"].str.lower() == industry.lower()].sort_values("RS", ascending=False)
        if result.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Industry not found. Available: {sorted(df['Industry'].unique().tolist())}",
            )
        return result.to_dict(orient="records")
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Run --update --market india first.")


# ── Inline HTML UI ────────────────────────────────────────────────────────────

_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RS Rating Pro</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px;
         line-height: 1.6; color: #1f2328; background: #f7f8fa; }
  header { background: #fff; border-bottom: 1px solid #e5e7eb; padding: 14px 28px;
           display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 700; }
  header a  { margin-left: auto; font-size: 12px; color: #3b82d4; text-decoration: none; }
  .tabs     { display: flex; gap: 0; border-bottom: 2px solid #e5e7eb;
              background: #fff; padding: 0 28px; }
  .tab      { padding: 10px 20px; cursor: pointer; font-size: 13px; font-weight: 500;
              border-bottom: 2px solid transparent; margin-bottom: -2px; color: #57606a;
              transition: color .15s, border-color .15s; }
  .tab.active { color: #1f2328; border-bottom-color: #3b82d4; }
  .main     { max-width: 1100px; margin: 24px auto; padding: 0 20px; }
  .card     { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
              padding: 20px 24px; margin-bottom: 20px; }
  .row      { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;
              margin-bottom: 4px; }
  input, select { border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px 12px;
                  font-size: 14px; outline: none; }
  input:focus, select:focus { border-color: #3b82d4; }
  button  { padding: 8px 20px; border-radius: 6px; border: none; font-size: 14px;
            cursor: pointer; font-weight: 500; transition: opacity .15s; }
  button:hover { opacity: .85; }
  .btn-primary { background: #3b82d4; color: #fff; }
  .btn-chart   { background: #7c5cd8; color: #fff; }
  .btn-clear   { background: #f3f4f6; color: #57606a; }
  .metrics  { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
              gap: 12px; margin-bottom: 20px; }
  .metric   { background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 8px;
              padding: 12px 14px; }
  .metric-label { font-size: 11px; color: #57606a; text-transform: uppercase;
                  letter-spacing: .04em; margin-bottom: 4px; }
  .metric-value { font-size: 22px; font-weight: 700; }
  .metric-value.rs-high  { color: #16a34a; }
  .metric-value.rs-mid   { color: #d97706; }
  .metric-value.rs-low   { color: #dc2626; }
  .badge    { display: inline-block; font-size: 12px; background: #f0f6ff;
              color: #3b82d4; border: 1px solid #bfdbfe; border-radius: 4px;
              padding: 2px 8px; margin: 0 4px 8px 0; }
  table     { width: 100%; border-collapse: collapse; font-size: 13px; }
  th        { background: #f7f8fa; text-align: left; padding: 8px 10px;
              border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #57606a;
              font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
  td        { padding: 7px 10px; border-bottom: 1px solid #f3f4f6; }
  tr:last-child td { border-bottom: none; }
  tr:hover td      { background: #f7f8fa; }
  .pos { color: #16a34a; } .neg { color: #dc2626; }
  .rs-pill { display: inline-block; padding: 1px 8px; border-radius: 999px;
             font-weight: 700; font-size: 12px; }
  .rs-pill.high { background: #dcfce7; color: #15803d; }
  .rs-pill.mid  { background: #fef3c7; color: #92400e; }
  .rs-pill.low  { background: #fee2e2; color: #991b1b; }
  #chart-container { min-height: 400px; }
  .spinner  { text-align: center; padding: 40px; color: #57606a; }
  .error    { background: #fee2e2; border: 1px solid #fca5a5; border-radius: 6px;
              padding: 12px 16px; color: #991b1b; margin-bottom: 16px; }
  #result   { display: none; }
  h3        { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #57606a;
              text-transform: uppercase; letter-spacing: .04em; }
  .section-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; }
</style>
</head>
<body>

<header>
  <span style="font-size:22px">📈</span>
  <h1>RS Rating Pro</h1>
  <span style="font-size:12px;color:#57606a">Relative Strength against S&amp;P 500 &amp; Nifty 750</span>
  <a href="/api-docs" target="_blank">API Docs →</a>
</header>

<div class="tabs">
  <div class="tab active" data-market="us"     onclick="switchMarket('us')">🇺🇸 S&amp;P 500</div>
  <div class="tab"        data-market="india"  onclick="switchMarket('india')">🇮🇳 Nifty 750</div>
</div>

<div class="main">
  <!-- Input card -->
  <div class="card">
    <div class="row">
      <div>
        <div style="font-size:11px;color:#57606a;margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em">Ticker Symbol</div>
        <input id="ticker-input" type="text" placeholder="e.g. AAPL" style="width:160px;text-transform:uppercase"
               onkeydown="if(event.key==='Enter') analyze()">
      </div>
      <button class="btn-primary" onclick="analyze()">Analyze</button>
      <button class="btn-chart"   onclick="analyzeChart()">Show Chart</button>
      <button class="btn-clear"   onclick="clearResult()">Clear</button>
    </div>
    <div id="market-hint" style="font-size:12px;color:#57606a;margin-top:6px">
      Enter NYSE/NASDAQ symbol — e.g. AAPL, NVDA, MSFT, PLTR
    </div>
  </div>

  <div id="error-box"  class="error"   style="display:none"></div>
  <div id="loading"    class="spinner" style="display:none">Fetching data…</div>

  <!-- Result section -->
  <div id="result">
    <!-- Metrics row -->
    <div class="metrics" id="metrics-row"></div>

    <!-- Badges -->
    <div id="badges" style="margin-bottom:16px"></div>

    <!-- Chart -->
    <div class="card" id="chart-card" style="display:none">
      <p class="section-title">Comparison Chart</p>
      <div id="chart-container"></div>
    </div>

    <!-- Period returns table -->
    <div class="card">
      <p class="section-title">Period Returns vs Benchmark Median</p>
      <table id="returns-table"></table>
    </div>
  </div>

  <!-- Top / Bottom tables (always visible) -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:4px" id="leaderboard">
    <div class="card">
      <p class="section-title">🏆 Top 10 by RS</p>
      <div id="top-table"><div class="spinner">Loading…</div></div>
    </div>
    <div class="card">
      <p class="section-title">📉 Bottom 10 by RS</p>
      <div id="bottom-table"><div class="spinner">Loading…</div></div>
    </div>
  </div>
</div>

<script>
let currentMarket = 'us';

function switchMarket(market) {
  currentMarket = market;
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.market === market));
  document.getElementById('ticker-input').value = '';
  document.getElementById('market-hint').textContent = market === 'india'
    ? 'Enter NSE symbol — e.g. RELIANCE, TCS, INFY, HDFCBANK, IDEAFORGE'
    : 'Enter NYSE/NASDAQ symbol — e.g. AAPL, NVDA, MSFT, PLTR';
  clearResult();
  loadLeaderboard();
}

/* ── Helpers ──────────────────────────────────────────────────────── */
function rsPill(rs) {
  const cls = rs >= 70 ? 'high' : rs >= 40 ? 'mid' : 'low';
  return `<span class="rs-pill ${cls}">${rs}</span>`;
}
function rsClass(rs) {
  return rs >= 70 ? 'rs-high' : rs >= 40 ? 'rs-mid' : 'rs-low';
}
function fmtPct(v) {
  const n = parseFloat(v);
  return `<span class="${n>=0?'pos':'neg'}">${n>=0?'+':''}${(n*100).toFixed(2)}%</span>`;
}
function fmtPctStr(v) {
  // v already a string like "+3.21%" or "-1.00%"
  const n = parseFloat(v);
  return `<span class="${n>=0?'pos':'neg'}">${v}</span>`;
}
function showError(msg) {
  const el = document.getElementById('error-box');
  el.textContent = msg; el.style.display = 'block';
}
function clearResult() {
  document.getElementById('result').style.display = 'none';
  document.getElementById('error-box').style.display = 'none';
  document.getElementById('chart-card').style.display = 'none';
  document.getElementById('chart-container').innerHTML = '';
}

/* ── Analyze (report only) ────────────────────────────────────────── */
async function analyze() {
  const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
  if (!ticker) return;
  clearResult();
  document.getElementById('loading').style.display = 'block';
  const url = currentMarket === 'india'
    ? `/india/stock/${ticker}`
    : `/stock/${ticker}`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) { showError(data.detail || 'Unknown error'); return; }
    renderReport(data);
  } catch(e) { showError('Network error: ' + e.message); }
  finally { document.getElementById('loading').style.display = 'none'; }
}

/* ── Analyze + Chart ──────────────────────────────────────────────── */
async function analyzeChart() {
  const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
  if (!ticker) return;
  clearResult();
  document.getElementById('loading').style.display = 'block';
  const stockUrl = currentMarket === 'india' ? `/india/stock/${ticker}` : `/stock/${ticker}`;
  const chartUrl = currentMarket === 'india' ? `/india/chart/${ticker}` : `/chart/${ticker}`;
  try {
    const [stockRes, chartRes] = await Promise.all([fetch(stockUrl), fetch(chartUrl)]);
    const data  = await stockRes.json();
    const figData = await chartRes.json();
    if (!stockRes.ok) { showError(data.detail || 'Unknown error'); return; }
    renderReport(data);
    renderChart(figData);
  } catch(e) { showError('Network error: ' + e.message); }
  finally { document.getElementById('loading').style.display = 'none'; }
}

/* ── Render report ────────────────────────────────────────────────── */
function renderReport(d) {
  // Metrics
  const metrics = [
    { label: 'RS Rating',   value: d.rs,                        cls: rsClass(d.rs) },
    { label: 'Percentile',  value: d.percentile.toFixed(1) + '%' },
    { label: 'Rank (Top)',  value: `#${d.rank_from_top} of ${d.total}` },
    { label: 'Wtd Score',   value: parseFloat(d.score).toFixed(4) },
    { label: '3M Return',   value: (d.return_3m*100>=0?'+':'') + (d.return_3m*100).toFixed(2)+'%',
      cls: d.return_3m >= 0 ? 'pos' : 'neg' },
    { label: '12M Return',  value: (d.return_12m*100>=0?'+':'') + (d.return_12m*100).toFixed(2)+'%',
      cls: d.return_12m >= 0 ? 'pos' : 'neg' },
  ];
  document.getElementById('metrics-row').innerHTML = metrics.map(m =>
    `<div class="metric">
       <div class="metric-label">${m.label}</div>
       <div class="metric-value ${m.cls||''}">${m.value}</div>
     </div>`).join('');

  // Badges
  const parts = [d.ticker, d.company, d.sector||d.industry].filter(Boolean);
  document.getElementById('badges').innerHTML =
    parts.map(p => `<span class="badge">${p}</span>`).join('') +
    (d.currency ? `<span class="badge">${d.currency}</span>` : '');

  // Returns table
  const periods = ['3m','6m','9m','12m'];
  const labels  = ['3M','6M','9M','12M'];
  document.getElementById('returns-table').innerHTML =
    `<thead><tr><th>Period</th><th>${d.ticker}</th><th>vs Benchmark</th></tr></thead>
     <tbody>` +
    periods.map((p,i) => {
      const v = d['return_'+p];
      const sign = v >= 0 ? '+' : '';
      const pctStr = sign + (v*100).toFixed(2) + '%';
      const cls = v >= 0 ? 'pos' : 'neg';
      return `<tr>
        <td><b>${labels[i]}</b></td>
        <td class="${cls}">${pctStr}</td>
        <td>${v >= 0 ? '▲' : '▼'} outperform check in chart</td>
      </tr>`;
    }).join('') + '</tbody>';

  document.getElementById('result').style.display = 'block';
}

/* ── Render chart ─────────────────────────────────────────────────── */
function renderChart(figData) {
  const card = document.getElementById('chart-card');
  card.style.display = 'block';
  Plotly.react('chart-container', figData.data, figData.layout, {responsive: true});
}

/* ── Leaderboard ──────────────────────────────────────────────────── */
async function loadLeaderboard() {
  const topUrl    = currentMarket === 'india' ? '/india/top?n=10'    : '/top?n=10';
  const bottomUrl = currentMarket === 'india' ? '/india/bottom?n=10' : '/bottom?n=10';

  async function buildTable(url, elId) {
    const el = document.getElementById(elId);
    el.innerHTML = '<div class="spinner">Loading…</div>';
    try {
      const res  = await fetch(url);
      const data = await res.json();
      const rows = data.map(r => {
        const sym = (r.NSE_Symbol || r.Ticker || '').replace('.NS','');
        const co  = r.Company || '';
        const ind = r.Industry || r.Sector || '';
        const ret = typeof r.Return_3m === 'number'
          ? (r.Return_3m>=0?'+':'') + (r.Return_3m*100).toFixed(1)+'%'
          : r.Return_3m || '';
        const retCls = typeof r.Return_3m === 'number' && r.Return_3m >= 0 ? 'pos' : 'neg';
        return `<tr>
          <td><b>${sym}</b></td>
          <td style="max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${co}</td>
          <td>${rsPill(r.RS)}</td>
          <td class="${retCls}">${ret}</td>
        </tr>`;
      }).join('');
      el.innerHTML =
        `<table><thead><tr><th>Ticker</th><th>Company</th><th>RS</th><th>3M Ret</th></tr></thead>
         <tbody>${rows}</tbody></table>`;
    } catch(e) { el.innerHTML = '<div class="error">Failed to load</div>'; }
  }

  buildTable(topUrl,    'top-table');
  buildTable(bottomUrl, 'bottom-table');
}

/* boot */
loadLeaderboard();
</script>

</body>
</html>
"""
