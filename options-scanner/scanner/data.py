"""Market data layer.

Two providers behind the same interface:

- YFinanceProvider: free live data from Yahoo Finance (stocks AND ETFs),
  with a small on-disk cache so re-running a scan doesn't hammer Yahoo.
- SyntheticProvider: deterministic Black-Scholes-generated chains, used for
  demo mode and the test suite (no network needed).
"""

from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, field

from . import bs

TRADING_DAYS = 252


@dataclass
class OptionQuote:
    strike: float
    bid: float
    ask: float
    iv: float                 # implied volatility, e.g. 0.32
    open_interest: int
    volume: int

    @property
    def mid(self) -> float:
        if self.bid <= 0 and self.ask <= 0:
            return 0.0
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pct(self) -> float:
        """Bid/ask spread as % of mid; liquidity sanity check."""
        m = self.mid
        return (self.ask - self.bid) / m if m > 0 else float("inf")


@dataclass
class ChainSnapshot:
    ticker: str
    spot: float
    expiry: dt.date
    puts: list[OptionQuote]
    calls: list[OptionQuote]

    @property
    def dte(self) -> int:
        return max((self.expiry - dt.date.today()).days, 0)


@dataclass
class UnderlyingInfo:
    ticker: str
    spot: float
    day_change_pct: float          # today's % move
    pct_off_52w_high: float        # negative = below high
    hist_vol_20d: float            # annualized 20-day realized vol
    rsi_14: float
    next_earnings: dt.date | None = None
    expiries: list[dt.date] = field(default_factory=list)
    sma_50: float = 0.0            # 50-day simple moving average
    boll_lower: float = 0.0        # 20-day Bollinger lower band (2σ)
    boll_upper: float = 0.0

    @property
    def entry_signals(self) -> frozenset:
        """Technical entry conditions for selling puts on this name.

        RSI<=30    — oversold
        LowerBB    — at/inside 2% of the lower Bollinger Band
        50SMA      — sitting at or just above the 50-day SMA (support)
        """
        sig = set()
        if self.rsi_14 <= 30:
            sig.add("RSI<=30")
        if self.boll_lower > 0 and self.spot <= self.boll_lower * 1.02:
            sig.add("LowerBB")
        if self.sma_50 > 0 and 0.99 <= self.spot / self.sma_50 <= 1.03:
            sig.add("50SMA")
        return frozenset(sig)


class DataProvider:
    """Interface both providers implement."""

    def underlying(self, ticker: str) -> UnderlyingInfo:
        raise NotImplementedError

    def chain(self, ticker: str, expiry: dt.date) -> ChainSnapshot:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Yahoo Finance provider (live data)
# ---------------------------------------------------------------------------

class YFinanceProvider(DataProvider):
    def __init__(self):
        import yfinance  # imported lazily so demo mode never needs it
        self._yf = yfinance
        self._tickers: dict[str, object] = {}
        self._info_cache: dict[str, UnderlyingInfo] = {}

    def _ticker(self, ticker: str):
        if ticker not in self._tickers:
            self._tickers[ticker] = self._yf.Ticker(ticker)
        return self._tickers[ticker]

    def underlying(self, ticker: str) -> UnderlyingInfo:
        if ticker in self._info_cache:
            return self._info_cache[ticker]
        t = self._ticker(ticker)
        hist = t.history(period="1y", auto_adjust=True)
        if hist.empty:
            raise ValueError(f"no price history for {ticker}")
        close = hist["Close"]
        spot = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else spot
        day_change = (spot / prev - 1.0) * 100.0
        high_52w = float(close.max())
        off_high = (spot / high_52w - 1.0) * 100.0

        rets = close.pct_change().dropna()
        recent = rets.tail(20)
        hv20 = float(recent.std() * math.sqrt(TRADING_DAYS)) if len(recent) > 2 else 0.0

        rsi = _rsi(close.tail(60).tolist(), 14)

        sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else spot
        last20 = close.tail(20)
        if len(last20) >= 20:
            mid = float(last20.mean())
            sd = float(last20.std())
            boll_lower, boll_upper = mid - 2 * sd, mid + 2 * sd
        else:
            boll_lower = boll_upper = 0.0

        next_earnings = None
        try:
            cal = t.get_earnings_dates(limit=8)
            if cal is not None and not cal.empty:
                today = dt.date.today()
                future = [d.date() for d in cal.index if d.date() >= today]
                if future:
                    next_earnings = min(future)
        except Exception:
            pass  # earnings data is best-effort; ETFs have none

        expiries = []
        try:
            expiries = [dt.date.fromisoformat(e) for e in t.options]
        except Exception:
            pass

        info = UnderlyingInfo(ticker, spot, day_change, off_high, hv20, rsi,
                              next_earnings, expiries,
                              sma_50=sma_50, boll_lower=boll_lower,
                              boll_upper=boll_upper)
        self._info_cache[ticker] = info
        return info

    def chain(self, ticker: str, expiry: dt.date) -> ChainSnapshot:
        t = self._ticker(ticker)
        oc = t.option_chain(expiry.isoformat())
        spot = self.underlying(ticker).spot
        return ChainSnapshot(
            ticker=ticker, spot=spot, expiry=expiry,
            puts=_frame_to_quotes(oc.puts),
            calls=_frame_to_quotes(oc.calls),
        )


def _frame_to_quotes(df) -> list[OptionQuote]:
    quotes = []
    for row in df.itertuples():
        iv = float(getattr(row, "impliedVolatility", 0) or 0)
        quotes.append(OptionQuote(
            strike=float(row.strike),
            bid=float(row.bid or 0),
            ask=float(row.ask or 0),
            iv=iv,
            open_interest=int(row.openInterest or 0),
            volume=int(row.volume or 0) if not _is_nan(row.volume) else 0,
        ))
    quotes.sort(key=lambda q: q.strike)
    return quotes


def _is_nan(x) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - 100.0 / (1.0 + rs)


# ---------------------------------------------------------------------------
# Synthetic provider (demo mode / tests)
# ---------------------------------------------------------------------------

class SyntheticProvider(DataProvider):
    """Deterministic fake market. Prices options with Black-Scholes off a
    seeded per-ticker spot/vol, so every screen has realistic-looking data."""

    def __init__(self, seed: int = 7):
        self.seed = seed

    def _rng(self, ticker: str) -> random.Random:
        return random.Random(f"{self.seed}:{ticker}")

    def _spot_iv(self, ticker: str) -> tuple[float, float]:
        rng = self._rng(ticker)
        spot = round(rng.uniform(25, 550), 2)
        iv = round(rng.uniform(0.16, 0.65), 3)
        return spot, iv

    def underlying(self, ticker: str) -> UnderlyingInfo:
        rng = self._rng(ticker)
        spot, iv = self._spot_iv(ticker)
        today = dt.date.today()
        expiries = [_next_friday(today, weeks) for weeks in (1, 2, 3, 4, 6, 8, 13)]
        earnings = None
        if rng.random() < 0.4:
            earnings = today + dt.timedelta(days=rng.randint(3, 45))
        return UnderlyingInfo(
            ticker=ticker, spot=spot,
            day_change_pct=round(rng.uniform(-4.5, 3.0), 2),
            pct_off_52w_high=round(rng.uniform(-35.0, -0.5), 2),
            hist_vol_20d=round(iv * rng.uniform(0.7, 1.1), 3),
            rsi_14=round(rng.uniform(22, 75), 1),
            next_earnings=earnings, expiries=expiries,
            sma_50=round(spot * rng.uniform(0.92, 1.12), 2),
            boll_lower=round(spot * rng.uniform(0.94, 1.01), 2),
            boll_upper=round(spot * rng.uniform(1.03, 1.10), 2),
        )

    def chain(self, ticker: str, expiry: dt.date) -> ChainSnapshot:
        rng = self._rng(ticker)
        spot, base_iv = self._spot_iv(ticker)
        t_years = max((expiry - dt.date.today()).days, 1) / 365.0
        step = _strike_step(spot)
        strikes = [round(k * step, 2) for k in range(int(spot * 0.6 / step), int(spot * 1.4 / step) + 1)]

        puts, calls = [], []
        for k in strikes:
            # crude vol smile: OTM puts richer (skew), far wings richer
            moneyness = math.log(k / spot)
            iv = base_iv * (1.0 + 0.35 * max(-moneyness, 0) + 0.10 * abs(moneyness))
            p = bs.put_price(spot, k, iv, t_years)
            c = bs.call_price(spot, k, iv, t_years)
            half_spread = max(0.01, p * 0.03)
            dist = abs(k - spot) / spot
            oi = int(max(0, rng.gauss(4000, 1500)) * math.exp(-6 * dist)) + 25
            vol = int(oi * rng.uniform(0.05, 0.4))
            puts.append(OptionQuote(k, round(max(p - half_spread, 0), 2),
                                    round(p + half_spread, 2), round(iv, 4), oi, vol))
            half_spread_c = max(0.01, c * 0.03)
            calls.append(OptionQuote(k, round(max(c - half_spread_c, 0), 2),
                                     round(c + half_spread_c, 2), round(iv, 4), oi, vol))
        return ChainSnapshot(ticker, spot, expiry, puts, calls)


def _next_friday(today: dt.date, weeks_out: int) -> dt.date:
    days_ahead = (4 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + dt.timedelta(days=days_ahead + 7 * (weeks_out - 1))


def _strike_step(spot: float) -> float:
    if spot < 25:
        return 0.5
    if spot < 100:
        return 1.0
    if spot < 250:
        return 2.5
    return 5.0
