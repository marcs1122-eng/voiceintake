"""Default scan universe.

Every symbol carries tags so scans can be filtered ("only ETFs", "only
blue-chips I'd be happy to own if assigned", "tech only", "high-IV premium
names"). Edit this file, or override with your own watchlist via the
sidebar/CLI.

Tags:
  etf         — exchange traded fund
  blue-chip   — quality name you'd be comfortable getting assigned (wheel-safe)
  dividend    — meaningful dividend while holding assigned shares
  growth      — growthier, more volatile, richer premium
  high-iv     — typically elevated implied vol; best for defined-risk spreads
  futures     — options on futures (chains need the tastytrade provider)
  sectors     — tech, semis, financials, healthcare, consumer, industrials,
                energy, materials, utilities, reits, china
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


DEFAULT_UNIVERSE: list[Symbol] = [
    # --- Index / broad ETFs ---
    _s("SPY", "etf", "blue-chip"), _s("QQQ", "etf", "blue-chip"),
    _s("IWM", "etf", "high-iv"), _s("DIA", "etf", "blue-chip"),
    # --- Sector / thematic ETFs ---
    _s("XLE", "etf", "energy", "dividend"), _s("XLF", "etf", "financials", "dividend"),
    _s("XLK", "etf", "tech"), _s("XLV", "etf", "healthcare", "dividend"),
    _s("XLU", "etf", "utilities", "dividend"), _s("XLI", "etf", "industrials"),
    _s("XLP", "etf", "consumer", "dividend"), _s("XLY", "etf", "consumer"),
    _s("XLB", "etf", "materials"), _s("XRT", "etf", "consumer", "high-iv"),
    _s("XHB", "etf", "consumer"), _s("SMH", "etf", "semis", "growth", "high-iv"),
    _s("XBI", "etf", "healthcare", "high-iv"), _s("IBB", "etf", "healthcare"),
    _s("KRE", "etf", "financials", "high-iv"), _s("XOP", "etf", "energy", "high-iv"),
    _s("OIH", "etf", "energy", "high-iv"), _s("GDX", "etf", "materials", "high-iv"),
    _s("GLD", "etf"), _s("SLV", "etf", "high-iv"), _s("TLT", "etf", "dividend"),
    _s("HYG", "etf", "dividend"), _s("EEM", "etf"), _s("EFA", "etf"),
    _s("FXI", "etf", "china", "high-iv"), _s("EWZ", "etf", "high-iv"),
    _s("ARKK", "etf", "high-iv", "growth"), _s("JETS", "etf", "high-iv"),
    _s("USO", "etf", "energy", "high-iv"), _s("URA", "etf", "high-iv"),
    # --- Mega-cap tech ---
    _s("AAPL", "tech", "blue-chip", "dividend"), _s("MSFT", "tech", "blue-chip", "dividend"),
    _s("GOOGL", "tech", "blue-chip"), _s("AMZN", "tech", "blue-chip", "growth"),
    _s("META", "tech", "blue-chip", "growth"), _s("NFLX", "tech", "growth"),
    _s("ORCL", "tech", "blue-chip", "dividend"), _s("CRM", "tech", "blue-chip"),
    _s("ADBE", "tech"), _s("NOW", "tech", "growth"), _s("INTU", "tech"),
    _s("IBM", "tech", "dividend"), _s("CSCO", "tech", "blue-chip", "dividend"),
    _s("ACN", "tech", "dividend"),
    # --- Software / internet growth ---
    _s("PLTR", "tech", "growth", "high-iv"), _s("SNOW", "tech", "growth", "high-iv"),
    _s("CRWD", "tech", "growth", "high-iv"), _s("PANW", "tech", "growth"),
    _s("NET", "tech", "growth", "high-iv"), _s("DDOG", "tech", "growth", "high-iv"),
    _s("SHOP", "tech", "growth", "high-iv"), _s("UBER", "tech", "growth"),
    _s("ABNB", "tech", "growth"), _s("DASH", "tech", "growth"),
    _s("RBLX", "tech", "growth", "high-iv"), _s("ROKU", "tech", "growth", "high-iv"),
    _s("HOOD", "financials", "growth", "high-iv"), _s("COIN", "financials", "growth", "high-iv"),
    _s("SOFI", "financials", "growth", "high-iv"), _s("PYPL", "financials", "growth", "high-iv"),
    _s("MSTR", "tech", "high-iv"), _s("SQ", "financials", "growth", "high-iv"),
    # --- Semis ---
    _s("NVDA", "semis", "growth", "high-iv"), _s("AMD", "semis", "growth", "high-iv"),
    _s("AVGO", "semis", "blue-chip", "dividend", "growth"), _s("TSM", "semis", "blue-chip"),
    _s("QCOM", "semis", "blue-chip", "dividend"), _s("TXN", "semis", "blue-chip", "dividend"),
    _s("MU", "semis", "growth", "high-iv"), _s("INTC", "semis", "high-iv"),
    _s("AMAT", "semis", "growth"), _s("LRCX", "semis", "growth"),
    _s("KLAC", "semis", "growth"), _s("ARM", "semis", "growth", "high-iv"),
    _s("SMCI", "semis", "high-iv"), _s("ON", "semis", "high-iv"),
    # --- Financials ---
    _s("JPM", "financials", "blue-chip", "dividend"), _s("BAC", "financials", "blue-chip", "dividend"),
    _s("WFC", "financials", "dividend"), _s("C", "financials", "dividend"),
    _s("GS", "financials", "blue-chip", "dividend"), _s("MS", "financials", "dividend"),
    _s("SCHW", "financials", "blue-chip"), _s("AXP", "financials", "blue-chip", "dividend"),
    _s("V", "financials", "blue-chip"), _s("MA", "financials", "blue-chip"),
    _s("BLK", "financials", "blue-chip", "dividend"), _s("BX", "financials", "dividend"),
    _s("KKR", "financials"), _s("COF", "financials"), _s("PGR", "financials", "blue-chip"),
    # --- Healthcare ---
    _s("UNH", "healthcare", "blue-chip", "dividend"), _s("LLY", "healthcare", "blue-chip", "growth"),
    _s("JNJ", "healthcare", "blue-chip", "dividend"), _s("ABBV", "healthcare", "blue-chip", "dividend"),
    _s("MRK", "healthcare", "blue-chip", "dividend"), _s("PFE", "healthcare", "dividend", "high-iv"),
    _s("NVO", "healthcare", "growth"), _s("AMGN", "healthcare", "dividend"),
    _s("GILD", "healthcare", "dividend"), _s("BMY", "healthcare", "dividend", "high-iv"),
    _s("CVS", "healthcare", "dividend", "high-iv"), _s("CI", "healthcare"),
    _s("MDT", "healthcare", "dividend"), _s("ISRG", "healthcare", "growth"),
    _s("VRTX", "healthcare"), _s("REGN", "healthcare", "high-iv"),
    _s("TMO", "healthcare", "blue-chip"),
    # --- Consumer ---
    _s("WMT", "consumer", "blue-chip", "dividend"), _s("COST", "consumer", "blue-chip"),
    _s("TGT", "consumer", "dividend", "high-iv"), _s("HD", "consumer", "blue-chip", "dividend"),
    _s("LOW", "consumer", "blue-chip", "dividend"), _s("TJX", "consumer", "blue-chip"),
    _s("ROST", "consumer"), _s("LULU", "consumer", "high-iv"),
    _s("NKE", "consumer", "blue-chip", "dividend"), _s("SBUX", "consumer", "blue-chip", "dividend"),
    _s("MCD", "consumer", "blue-chip", "dividend"), _s("CMG", "consumer", "growth"),
    _s("YUM", "consumer", "dividend"), _s("DPZ", "consumer"),
    _s("KO", "consumer", "blue-chip", "dividend"), _s("PEP", "consumer", "blue-chip", "dividend"),
    _s("PG", "consumer", "blue-chip", "dividend"), _s("MDLZ", "consumer", "dividend"),
    _s("MO", "consumer", "dividend"), _s("PM", "consumer", "dividend"),
    _s("STZ", "consumer", "dividend"), _s("EL", "consumer", "high-iv"),
    _s("DIS", "consumer", "blue-chip"), _s("MAR", "consumer"),
    _s("RCL", "consumer", "high-iv"), _s("CCL", "consumer", "high-iv"),
    _s("LVS", "consumer", "high-iv"), _s("MGM", "consumer", "high-iv"),
    _s("DKNG", "consumer", "growth", "high-iv"), _s("TSLA", "consumer", "growth", "high-iv"),
    _s("F", "consumer", "dividend", "high-iv"), _s("GM", "consumer", "high-iv"),
    _s("RIVN", "consumer", "high-iv"), _s("LCID", "consumer", "high-iv"),
    # --- Industrials / defense / transport ---
    _s("CAT", "industrials", "blue-chip", "dividend"), _s("DE", "industrials", "blue-chip", "dividend"),
    _s("GE", "industrials", "blue-chip"), _s("HON", "industrials", "dividend"),
    _s("MMM", "industrials", "dividend"), _s("RTX", "industrials", "dividend"),
    _s("LMT", "industrials", "dividend"), _s("NOC", "industrials", "dividend"),
    _s("BA", "industrials", "high-iv"), _s("UPS", "industrials", "dividend", "high-iv"),
    _s("FDX", "industrials", "dividend"), _s("UNP", "industrials", "dividend"),
    _s("CSX", "industrials", "dividend"), _s("ETN", "industrials", "growth"),
    _s("EMR", "industrials", "dividend"), _s("DAL", "industrials", "high-iv"),
    _s("UAL", "industrials", "high-iv"), _s("LUV", "industrials", "high-iv"),
    _s("AAL", "industrials", "high-iv"),
    # --- Energy / materials ---
    _s("XOM", "energy", "blue-chip", "dividend"), _s("CVX", "energy", "blue-chip", "dividend"),
    _s("COP", "energy", "dividend"), _s("OXY", "energy", "high-iv"),
    _s("SLB", "energy", "dividend", "high-iv"), _s("HAL", "energy", "high-iv"),
    _s("DVN", "energy", "dividend", "high-iv"), _s("EOG", "energy", "dividend"),
    _s("MPC", "energy", "dividend"), _s("VLO", "energy", "dividend"),
    _s("PSX", "energy", "dividend"), _s("KMI", "energy", "dividend"),
    _s("WMB", "energy", "dividend"), _s("FCX", "materials", "high-iv"),
    _s("NEM", "materials", "dividend", "high-iv"), _s("NUE", "materials", "dividend"),
    _s("CLF", "materials", "high-iv"), _s("AA", "materials", "high-iv"),
    # --- Utilities / REITs / income ---
    _s("NEE", "utilities", "blue-chip", "dividend"), _s("SO", "utilities", "dividend"),
    _s("DUK", "utilities", "dividend"), _s("D", "utilities", "dividend"),
    _s("AEP", "utilities", "dividend"), _s("EXC", "utilities", "dividend"),
    _s("O", "reits", "blue-chip", "dividend"), _s("AMT", "reits", "dividend"),
    _s("PLD", "reits", "dividend"), _s("SPG", "reits", "dividend"),
    _s("VICI", "reits", "dividend"), _s("EQIX", "reits", "dividend"),
    _s("T", "dividend"), _s("VZ", "dividend"),
    # --- China / intl ADRs ---
    _s("BABA", "china", "high-iv"), _s("JD", "china", "high-iv"),
    _s("PDD", "china", "high-iv"), _s("NIO", "china", "high-iv"),
    _s("BIDU", "china", "high-iv"),
    # --- Liquid futures (options on futures; chains require the
    #     tastytrade provider — Yahoo only feeds their technicals/dips) ---
    _s("/ES", "futures", "blue-chip"), _s("/NQ", "futures", "blue-chip"),
    _s("/CL", "futures", "energy", "high-iv"), _s("/GC", "futures"),
    _s("/SI", "futures", "high-iv"), _s("/ZB", "futures"),
    _s("/ZN", "futures"), _s("/NG", "futures", "energy", "high-iv"),
    _s("/ZC", "futures"), _s("/ZS", "futures"), _s("/ZW", "futures"),
    _s("/6E", "futures"),
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
