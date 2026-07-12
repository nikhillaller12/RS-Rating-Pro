from .config import LOOKBACKS, WEIGHTS


def score(series):
    """
    Compute the weighted RS score from a price Series.

    LOOKBACKS defines non-overlapping quarterly slices so that no single
    period dominates and overlapping returns don't double-count performance.

    Also returns the cumulative period returns (measured from today back)
    that are displayed in the report.
    """
    s = series.dropna()

    if len(s) < 252:
        raise ValueError(f"Need at least 252 trading days, got {len(s)}")

    # Non-overlapping quarterly returns (used for the weighted score)
    quarterly = {}
    for k, (start, end) in LOOKBACKS.items():
        price_start = s.iloc[-(end)]      # older price
        price_end   = s.iloc[-(start+1)] if start > 0 else s.iloc[-1]
        quarterly[k] = price_end / price_start - 1

    weighted = sum(quarterly[k] * WEIGHTS[k] for k in quarterly)

    # Cumulative returns from today (for display in the report)
    latest = s.iloc[-1]
    cumulative = {
        "3m":  latest / s.iloc[-63]  - 1,
        "6m":  latest / s.iloc[-126] - 1,
        "9m":  latest / s.iloc[-189] - 1,
        "12m": latest / s.iloc[-252] - 1,
    }

    return weighted, cumulative
