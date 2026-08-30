"""Liquid futures products for selling options on futures.

Futures puts are margin-secured, not cash-secured, so return-on-capital is
computed against an initial-margin estimate instead of strike × 100. The
margin numbers below are rough exchange initial margins for one short
option / one contract — SPAN margin moves with volatility, so update them
every month or two (your tastytrade platform shows the live number per
trade). Multiplier is $ per point of the underlying future.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesProduct:
    symbol: str            # tastytrade root, e.g. "/ES"
    name: str
    yahoo_symbol: str      # continuous contract on Yahoo for price history
    multiplier: float      # $ per 1.00 move in the underlying
    margin_estimate: float # approx initial margin per contract, USD


FUTURES_PRODUCTS: list[FuturesProduct] = [
    FuturesProduct("/ES", "E-mini S&P 500", "ES=F", 50.0, 17_000),
    FuturesProduct("/MES", "Micro E-mini S&P 500", "ES=F", 5.0, 1_700),
    FuturesProduct("/NQ", "E-mini Nasdaq-100", "NQ=F", 20.0, 26_000),
    FuturesProduct("/MNQ", "Micro E-mini Nasdaq-100", "NQ=F", 2.0, 2_600),
    FuturesProduct("/CL", "Crude Oil", "CL=F", 1_000.0, 6_500),
    FuturesProduct("/MCL", "Micro Crude Oil", "CL=F", 100.0, 650),
    FuturesProduct("/GC", "Gold", "GC=F", 100.0, 13_000),
    FuturesProduct("/MGC", "Micro Gold", "GC=F", 10.0, 1_300),
    FuturesProduct("/SI", "Silver", "SI=F", 5_000.0, 16_000),
    FuturesProduct("/ZB", "30-Year T-Bond", "ZB=F", 1_000.0, 4_800),
    FuturesProduct("/ZN", "10-Year T-Note", "ZN=F", 1_000.0, 3_200),
    FuturesProduct("/NG", "Natural Gas", "NG=F", 10_000.0, 3_800),
    FuturesProduct("/ZC", "Corn", "ZC=F", 50.0, 1_500),
    FuturesProduct("/ZS", "Soybeans", "ZS=F", 50.0, 2_600),
    FuturesProduct("/ZW", "Wheat", "ZW=F", 50.0, 2_100),
    FuturesProduct("/6E", "Euro FX", "6E=F", 125_000.0, 2_700),
]

FUTURES_BY_SYMBOL: dict[str, FuturesProduct] = {p.symbol: p for p in FUTURES_PRODUCTS}


def is_futures(ticker: str) -> bool:
    return ticker.startswith("/")


def product_for(ticker: str) -> FuturesProduct | None:
    return FUTURES_BY_SYMBOL.get(ticker)
