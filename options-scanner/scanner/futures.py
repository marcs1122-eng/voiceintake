"""Liquid futures products for selling options on futures.

Futures puts are margin-secured, not cash-secured, so return-on-capital is
computed against an initial-margin estimate instead of strike × 100. The
margin numbers below are rough exchange initial margins for one short
option / one contract — SPAN margin moves with volatility, so update them
every month or two (your tastytrade platform shows the live number per
trade). Multiplier is $ per 1.00 point of the underlying price as quoted.

`tier` is options liquidity, not futures liquidity — the two differ a lot:
    1 = deep, tight options books; work limits at mid and expect fills
    2 = tradeable but thinner; be picky, wider spreads, smaller size
    3 = thin/speculative options; scan them, but treat fills as a fight

`corr_es` is the measured 90-day daily-return correlation to /ES (the
equity benchmark). Low |corr| = genuine diversification for a book that is
already long equity risk. Refresh periodically; regimes change.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesProduct:
    symbol: str            # tastytrade root, e.g. "/ES"
    name: str
    yahoo_symbol: str      # continuous contract on Yahoo for price history
    multiplier: float      # $ per 1.00 move in the underlying
    margin_estimate: float # approx initial margin per contract, USD
    tier: int = 2          # options-liquidity tier (1 best)
    corr_es: float = 0.0   # 90d daily-return correlation to /ES
    group: str = ""        # equity-index / energy / metals / rates / fx / ags / crypto


FUTURES_PRODUCTS: list[FuturesProduct] = [
    # --- Equity index: the deepest options books in all of futures ---
    FuturesProduct("/ES", "E-mini S&P 500", "ES=F", 50.0, 17_000, 1, 1.00, "equity-index"),
    FuturesProduct("/MES", "Micro E-mini S&P 500", "ES=F", 5.0, 1_700, 1, 1.00, "equity-index"),
    FuturesProduct("/NQ", "E-mini Nasdaq-100", "NQ=F", 20.0, 26_000, 1, 0.91, "equity-index"),
    FuturesProduct("/MNQ", "Micro E-mini Nasdaq-100", "NQ=F", 2.0, 2_600, 1, 0.91, "equity-index"),
    FuturesProduct("/RTY", "E-mini Russell 2000", "RTY=F", 50.0, 8_500, 2, 0.79, "equity-index"),
    FuturesProduct("/M2K", "Micro E-mini Russell 2000", "RTY=F", 5.0, 850, 2, 0.79, "equity-index"),
    # --- Energy ---
    FuturesProduct("/CL", "Crude Oil", "CL=F", 1_000.0, 6_500, 1, -0.38, "energy"),
    FuturesProduct("/MCL", "Micro Crude Oil", "CL=F", 100.0, 650, 2, -0.38, "energy"),
    FuturesProduct("/NG", "Henry Hub Natural Gas", "NG=F", 10_000.0, 3_800, 1, -0.04, "energy"),
    # --- Metals ---
    FuturesProduct("/GC", "Gold", "GC=F", 100.0, 13_000, 1, 0.46, "metals"),
    FuturesProduct("/MGC", "Micro Gold", "GC=F", 10.0, 1_300, 2, 0.46, "metals"),
    FuturesProduct("/SI", "Silver", "SI=F", 5_000.0, 16_000, 1, 0.44, "metals"),
    FuturesProduct("/SIL", "Micro Silver", "SI=F", 1_000.0, 3_200, 2, 0.44, "metals"),
    FuturesProduct("/HG", "Copper", "HG=F", 25_000.0, 8_000, 2, 0.57, "metals"),
    # --- Rates (note: the whole complex is ~0.9 correlated to itself) ---
    FuturesProduct("/ZN", "10-Year T-Note", "ZN=F", 1_000.0, 3_200, 1, 0.45, "rates"),
    FuturesProduct("/ZB", "30-Year T-Bond", "ZB=F", 1_000.0, 4_800, 1, 0.39, "rates"),
    FuturesProduct("/ZF", "5-Year T-Note", "ZF=F", 1_000.0, 2_300, 2, 0.46, "rates"),
    FuturesProduct("/ZT", "2-Year T-Note", "ZT=F", 2_000.0, 1_500, 2, 0.43, "rates"),
    # --- FX ---
    FuturesProduct("/6E", "Euro FX", "6E=F", 125_000.0, 2_700, 1, 0.41, "fx"),
    FuturesProduct("/6J", "Japanese Yen", "6J=F", 12_500_000.0, 3_500, 2, 0.26, "fx"),
    FuturesProduct("/6B", "British Pound", "6B=F", 62_500.0, 2_200, 2, 0.31, "fx"),
    FuturesProduct("/6A", "Australian Dollar", "6A=F", 100_000.0, 1_900, 2, 0.60, "fx"),
    FuturesProduct("/6C", "Canadian Dollar", "6C=F", 100_000.0, 1_600, 2, 0.09, "fx"),
    # --- Grains / softs: the truest diversifiers vs an equity book ---
    FuturesProduct("/ZC", "Corn", "ZC=F", 50.0, 1_500, 1, -0.01, "ags"),
    FuturesProduct("/ZS", "Soybeans", "ZS=F", 50.0, 2_600, 1, -0.07, "ags"),
    FuturesProduct("/ZW", "Chicago Wheat", "ZW=F", 50.0, 2_100, 2, -0.03, "ags"),
    # --- Meats: thin options, but genuinely uncorrelated ---
    FuturesProduct("/HE", "Lean Hogs", "HE=F", 400.0, 2_000, 3, 0.18, "ags"),
    FuturesProduct("/LE", "Live Cattle", "LE=F", 400.0, 3_000, 3, -0.10, "ags"),
    # --- Crypto: options exist but books are wide; micros only, small size ---
    FuturesProduct("/MBT", "Micro Bitcoin", "BTC-USD", 0.1, 2_000, 3, 0.36, "crypto"),
    FuturesProduct("/MET", "Micro Ether", "ETH-USD", 0.1, 700, 3, 0.42, "crypto"),
]

FUTURES_BY_SYMBOL: dict[str, FuturesProduct] = {p.symbol: p for p in FUTURES_PRODUCTS}

# Products deliberately NOT included, and why:
#   /SR3  SOFR — options are an institutional rates product; retail books are
#         effectively unquotable and the underlying barely moves.
#   /BTC /ETH full-size — ~$390k and ~$123k notional; margin dwarfs the
#         premium. Trade /MBT and /MET instead.


def is_futures(ticker: str) -> bool:
    return ticker.startswith("/")


def product_for(ticker: str) -> FuturesProduct | None:
    return FUTURES_BY_SYMBOL.get(ticker)
