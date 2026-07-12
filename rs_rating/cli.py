import argparse
from .engine import update, lookup, update_india, lookup_india
from .charts import open_chart


def _print_report(r, market="us"):
    flag = "🇮🇳" if market == "india" else "🇺🇸"
    sep  = "=" * 53
    print(sep)
    print(f"  {flag} Relative Strength Report")
    print(sep)
    print(f"  Ticker        : {r['ticker']}")
    if r.get("company"):
        print(f"  Company       : {r['company']}")
    if r.get("sector"):
        print(f"  Sector        : {r['sector']}")
    if r.get("industry"):
        print(f"  Industry      : {r['industry']}")
    if market == "india":
        print(f"  Currency      : INR (₹)")
    print()
    print(f"  3M Return     : {r['return_3m']:+.2%}")
    print(f"  6M Return     : {r['return_6m']:+.2%}")
    print(f"  9M Return     : {r['return_9m']:+.2%}")
    print(f"  12M Return    : {r['return_12m']:+.2%}")
    print()
    print(f"  Weighted Score: {r['score']:.4f}")
    print()
    bench_name = "Nifty 750" if market == "india" else "S&P 500"
    print(f"  Benchmark     : {bench_name}")
    print(f"  Rank          : #{r['rank_from_top']} of {r['total']}  (1 = strongest)")
    print(f"  Percentile    : {r['percentile']:.2f}%")
    print()
    print(f"  RS Rating     : {r['rs']}")
    print(sep)


def main():
    p = argparse.ArgumentParser(description="RS Rating Pro — Relative Strength CLI")
    p.add_argument("ticker", nargs="?", help="Ticker symbol to look up")
    p.add_argument("--update", action="store_true", help="Rebuild the benchmark")
    p.add_argument("--chart",  action="store_true", help="Open interactive comparison chart")
    p.add_argument(
        "--market", choices=["us", "india"], default="us",
        help="Market universe: 'us' (S&P 500) or 'india' (Nifty 750). Default: us"
    )
    a = p.parse_args()

    if a.update:
        if a.market == "india":
            update_india()
            print("India benchmark (Nifty 750) updated.")
        else:
            update()
            print("US benchmark (S&P 500) updated.")

    elif a.ticker:
        t = a.ticker.upper()
        if a.market == "india":
            if a.chart:
                open_chart(t, market="india")
            else:
                _print_report(lookup_india(t), market="india")
        else:
            if a.chart:
                open_chart(t, market="us")
            else:
                _print_report(lookup(t), market="us")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
