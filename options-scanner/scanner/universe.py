"""Default scan universe.

Every symbol carries tags so scans can be filtered ("only ETFs", "only
blue-chips I'd be happy to own if assigned", "high-IV premium names").
Edit this file, or override with your own watchlist via config/CLI.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Symbol:
    ticker: str
    tags: frozenset = field(default_factory=frozenset)

    def has(self, tag: str) -> bool:
        return tag in self.tags


def _s(ticker: str, *tags: str) -> Symbol:
    return Symbol(ticker, frozenset(tags))


# Tags:
#   etf        — exchange traded fund (index or sector)
#   blue-chip  — quality name you'd be comfortable getting assigned (wheel-safe)
#   dividend   — meaningful dividend while you hold assigned shares
#   growth     — growthier, more volatile, richer premium
#   high-iv    — typically elevated implied vol; best for defined-risk spreads
DEFAULT_UNIVERSE: list[Symbol] = [
    # --- Index / broad ETFs ---
    _s("SPY", "etf", "blue-chip"),
    _s("QQQ", "etf", "blue-chip"),
    _s("IWM", "etf", "high-iv"),
    _s("DIA", "etf", "blue-chip"),
    # --- Sector / thematic ETFs ---
    _s("XLE", "etf", "dividend"),
    _s("XLF", "etf", "dividend"),
    _s("XLK", "etf"),
    _s("XLV", "etf", "dividend"),
    _s("XLU", "etf", "dividend"),
    _s("SMH", "etf", "growth", "high-iv"),
    _s("XBI", "etf", "high-iv"),
    _s("KRE", "etf", "high-iv"),
    _s("GLD", "etf"),
    _s("SLV", "etf", "high-iv"),
    _s("TLT", "etf", "dividend"),
    _s("EEM", "etf"),
    _s("FXI", "etf", "high-iv"),
    _s("ARKK", "etf", "high-iv", "growth"),
    _s("USO", "etf", "high-iv"),
    # --- Mega-cap tech ---
    _s("AAPL", "blue-chip", "dividend"),
    _s("MSFT", "blue-chip", "dividend"),
    _s("GOOGL", "blue-chip"),
    _s("AMZN", "blue-chip", "growth"),
    _s("NVDA", "growth", "high-iv"),
    _s("META", "blue-chip", "growth"),
    _s("AVGO", "blue-chip", "dividend", "growth"),
    _s("AMD", "growth", "high-iv"),
    _s("TSLA", "growth", "high-iv"),
    _s("ORCL", "blue-chip", "dividend"),
    _s("CRM", "blue-chip"),
    _s("QCOM", "blue-chip", "dividend"),
    _s("TXN", "blue-chip", "dividend"),
    _s("MU", "growth", "high-iv"),
    _s("INTC", "high-iv"),
    _s("CSCO", "blue-chip", "dividend"),
    _s("PLTR", "growth", "high-iv"),
    _s("SHOP", "growth", "high-iv"),
    _s("UBER", "growth"),
    _s("ABNB", "growth"),
    _s("COIN", "growth", "high-iv"),
    _s("SOFI", "growth", "high-iv"),
    _s("PYPL", "growth", "high-iv"),
    # --- Financials ---
    _s("JPM", "blue-chip", "dividend"),
    _s("BAC", "blue-chip", "dividend"),
    _s("GS", "blue-chip", "dividend"),
    _s("V", "blue-chip"),
    _s("MA", "blue-chip"),
    # --- Consumer / staples ---
    _s("WMT", "blue-chip", "dividend"),
    _s("COST", "blue-chip"),
    _s("KO", "blue-chip", "dividend"),
    _s("PEP", "blue-chip", "dividend"),
    _s("PG", "blue-chip", "dividend"),
    _s("MCD", "blue-chip", "dividend"),
    _s("SBUX", "blue-chip", "dividend"),
    _s("NKE", "blue-chip", "dividend"),
    _s("DIS", "blue-chip"),
    _s("HD", "blue-chip", "dividend"),
    _s("LOW", "blue-chip", "dividend"),
    # --- Healthcare ---
    _s("UNH", "blue-chip", "dividend"),
    _s("JNJ", "blue-chip", "dividend"),
    _s("ABBV", "blue-chip", "dividend"),
    _s("MRK", "blue-chip", "dividend"),
    _s("PFE", "dividend", "high-iv"),
    # --- Energy / industrial / autos ---
    _s("XOM", "blue-chip", "dividend"),
    _s("CVX", "blue-chip", "dividend"),
    _s("CAT", "blue-chip", "dividend"),
    _s("DE", "blue-chip", "dividend"),
    _s("GE", "blue-chip"),
    _s("BA", "high-iv"),
    _s("F", "dividend", "high-iv"),
    _s("GM", "high-iv"),
    _s("DAL", "high-iv"),
    _s("UAL", "high-iv"),
    # --- Income / REIT ---
    _s("O", "blue-chip", "dividend"),
    _s("T", "dividend"),
    _s("VZ", "dividend"),
]


def filter_universe(universe: list[Symbol], include_tags: set[str] | None = None,
                    exclude_tags: set[str] | None = None,
                    tickers: set[str] | None = None) -> list[Symbol]:
    """Filter a universe by tag membership and/or an explicit ticker set."""
    out = []
    for sym in universe:
        if tickers is not None and sym.ticker not in tickers:
            continue
        if include_tags and not (sym.tags & include_tags):
            continue
        if exclude_tags and (sym.tags & exclude_tags):
            continue
        out.append(sym)
    return out
