"""Portfolio correlation analysis — PowerX-style.

Given a set of underlyings (usually the tickers behind your open positions),
fetch ~3 months of daily closes, compute the pairwise correlation of daily
returns, and surface: the matrix, the hot (too-correlated) pairs, each
name's average correlation to the rest of the book, and which diversifiers
would actually lower the book's correlation.
"""

from __future__ import annotations

from .futures import product_for

# Index roots that show up as position underlyings -> Yahoo symbols
INDEX_MAP = {
    "SPX": "^SPX", "SPXW": "^SPX", "XSP": "^XSP",
    "NDX": "^NDX", "NDXP": "^NDX",
    "RUT": "^RUT", "RUTW": "^RUT", "VIX": "^VIX",
}

# Candidate diversifiers checked against the book (label, yahoo symbol)
DIVERSIFIERS = [
    ("GLD (gold)", "GLD"), ("TLT (long bonds)", "TLT"),
    ("XLU (utilities)", "XLU"), ("XLP (staples)", "XLP"),
    ("XLV (healthcare)", "XLV"), ("XLE (energy)", "XLE"),
    ("FXI (china)", "FXI"), ("IWM (small caps)", "IWM"),
    ("/ZN via ZN=F (rates)", "ZN=F"), ("USO (oil)", "USO"),
]


def yahoo_symbol_for(underlying: str) -> str:
    """Map a position underlying to a Yahoo history symbol."""
    u = (underlying or "").strip().upper()
    prod = product_for(u)
    if prod:
        return prod.yahoo_symbol
    if u.startswith("/"):
        # unknown future root: try the continuous-contract convention
        return u.lstrip("/")[:2] + "=F"
    return INDEX_MAP.get(u, u)


def fetch_closes(symbols: list[str], period: str = "3mo"):
    """Daily closes DataFrame (columns = requested symbols), via Yahoo."""
    import pandas as pd
    import yfinance as yf

    mapping = {s: yahoo_symbol_for(s) for s in symbols}
    raw = yf.download(sorted(set(mapping.values())), period=period,
                      interval="1d", auto_adjust=True, progress=False)["Close"]
    if hasattr(raw, "to_frame") and raw.ndim == 1:  # single symbol
        raw = raw.to_frame(name=list(mapping.values())[0])
    out = pd.DataFrame({label: raw[ysym] for label, ysym in mapping.items()
                        if ysym in raw.columns})
    return out.dropna(how="all")


def corr_matrix(closes):
    """Pairwise correlation of daily returns; drops symbols with <15 bars."""
    rets = closes.pct_change().dropna(how="all")
    rets = rets.loc[:, rets.count() >= 15]
    return rets.corr().round(2)


def analyze(matrix) -> dict:
    """Read the matrix like a risk manager.

    Returns dict with:
      portfolio_avg  — average pairwise correlation across the book
      avg_by_symbol  — {symbol: avg corr to everything else}, most-correlated first
      hot_pairs      — [(a, b, corr)] with corr >= 0.70, highest first
    """
    import numpy as np

    syms = list(matrix.columns)
    pairs, hot = [], []
    for i, a in enumerate(syms):
        for b in syms[i + 1:]:
            c = matrix.loc[a, b]
            if np.isnan(c):
                continue
            pairs.append(c)
            if c >= 0.70:
                hot.append((a, b, float(c)))
    hot.sort(key=lambda t: -t[2])

    avg_by_symbol = {}
    for a in syms:
        others = [matrix.loc[a, b] for b in syms if b != a and not np.isnan(matrix.loc[a, b])]
        if others:
            avg_by_symbol[a] = float(np.mean(others))
    avg_by_symbol = dict(sorted(avg_by_symbol.items(), key=lambda kv: -kv[1]))

    return {
        "portfolio_avg": float(np.mean(pairs)) if pairs else 0.0,
        "avg_by_symbol": avg_by_symbol,
        "hot_pairs": hot,
    }


def rate_portfolio(avg: float) -> str:
    if avg >= 0.60:
        return "🔴 Heavily correlated — this book moves as one trade"
    if avg >= 0.40:
        return "🟠 Elevated — a broad selloff hits most positions at once"
    if avg >= 0.20:
        return "🟡 Moderate — reasonable spread, some clustering"
    return "🟢 Well diversified"


def candidate_fit(candidates: list[str], held: list[str],
                  closes=None) -> dict[str, float | None]:
    """How each candidate would sit in the current book: its average
    correlation to every held underlying (None when unmeasurable). Pass a
    closes DataFrame to skip the fetch (tests, cached sessions)."""
    held = [h for h in dict.fromkeys(held) if h]
    cands = [c for c in dict.fromkeys(candidates) if c]
    if not held or not cands:
        return {c: None for c in cands}
    if closes is None:
        closes = fetch_closes(sorted(set(held) | set(cands)))
    m = corr_matrix(closes)
    out: dict[str, float | None] = {}
    for c in cands:
        if c not in m.columns:
            out[c] = None
            continue
        vals = [float(m.loc[c, h]) for h in held
                if h in m.columns and h != c and not _isnan(m.loc[c, h])]
        out[c] = (sum(vals) / len(vals)) if vals else None
    return out


def fit_label(avg: float | None, hot: float = 0.60) -> str:
    """One phrase for the Trade Plan card."""
    if avg is None:
        return "no book data"
    if avg >= hot:
        return f"⚠️ you already own this risk (avg ρ {avg:.2f})"
    if avg >= 0.40:
        return f"overlaps the book (avg ρ {avg:.2f})"
    if avg >= 0.20:
        return f"neutral fit (avg ρ {avg:.2f})"
    return f"adds diversification (avg ρ {avg:.2f})"


def _isnan(x) -> bool:
    try:
        return x != x
    except Exception:
        return True


def diversification_ideas(held: list[str]) -> list[tuple[str, str, float]]:
    """[(label, yahoo symbol, avg corr to the book)] lowest first, using the
    same closes the Correlation tab uses. Held names already in the
    diversifier list are skipped."""
    div_syms = [y for _, y in DIVERSIFIERS if y not in held]
    closes = fetch_closes(list(held) + div_syms)
    m = corr_matrix(closes)
    book = [h for h in held if h in m.columns]
    ideas = []
    for label, ysym in DIVERSIFIERS:
        if ysym in m.columns and ysym not in book:
            vals = [m.loc[ysym, h] for h in book if not _isnan(m.loc[ysym, h])]
            if vals:
                ideas.append((label, ysym, float(sum(vals) / len(vals))))
    ideas.sort(key=lambda t: t[2])
    return ideas
