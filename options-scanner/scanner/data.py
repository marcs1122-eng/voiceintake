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
    multiplier: float = 100.0      # $ per 1.00 of premium (100 for equity options)

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
    sma_50: float = 0.0            # 50-bar simple moving average (on the scan timeframe)
    boll_lower: float = 0.0        # 20-bar Bollinger lower band, 2σ (on the scan timeframe)
    boll_upper: float = 0.0
    day_high: float = 0.0          # today's session high
    day_low: float = 0.0           # today's session low

    # --- volatility context (tastytrade market metrics when live; the Yahoo
    #     path fills iv_rank with a realized-vol rank as a labelled proxy) ---
    iv_rank: float | None = None        # 0-100: where current IV sits in its 1-yr range
    iv_percentile: float | None = None  # 0-100: % of days in the past year IV was lower
    iv_index: float | None = None       # current implied vol, 0.32 = 32%
    hv_30: float | None = None          # 30-day realized vol
    beta: float | None = None
    corr_spy: float | None = None       # 3-month correlation to SPY
    liquidity_rating: int | None = None # tastytrade 1 (worst) .. 4 (best)
    dividend_yield: float = 0.0         # annual, 0.03 = 3%
    iv_source: str = ""                 # "tastytrade" | "hv-proxy" | ""

    def expected_move(self, dte: int, iv: float | None = None) -> float:
        """1-sigma move to expiry in price units. Uses the given IV, else
        the IV index, else realized vol as a last resort."""
        from . import bs
        vol = iv or self.iv_index or self.hist_vol_20d
        return bs.expected_move(self.spot, vol or 0.0, dte)

    @property
    def at_day_low(self) -> bool:
        """Within 0.3% of today's low — scalp-entry zone for premium sellers."""
        return self.day_low > 0 and self.spot <= self.day_low * 1.003

    @property
    def at_day_high(self) -> bool:
        return self.day_high > 0 and self.spot >= self.day_high * 0.997

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

    def prefetch(self, tickers: list[str]) -> None:
        """Optional bulk warm-up before a scan (e.g. one market-metrics call
        for the whole universe). Default: nothing."""

    def expiry_iv(self, ticker: str, expiry: dt.date) -> float | None:
        """Provider-supplied ATM implied vol for one expiration, if it has
        one (tastytrade does). None → the scan derives it from the chain."""
        return None

    def history_lows(self, ticker: str, since: dt.date) -> float | None:
        """Lowest trade since `since` (inclusive) — used by the track record
        to tell whether a short strike was ever tested. None if unknown."""
        return None

    def underlying(self, ticker: str) -> UnderlyingInfo:
        raise NotImplementedError

    def chain(self, ticker: str, expiry: dt.date) -> ChainSnapshot:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Yahoo Finance provider (live data)
# ---------------------------------------------------------------------------

# Signal timeframe → (yfinance interval, fetch period, pandas resample rule).
# Yahoo has no native 10m or 4h bars, so those resample from 5m/60m.
TIMEFRAMES: dict[str, tuple[str, str, str | None]] = {
    "5m": ("5m", "5d", None),
    "10m": ("5m", "5d", "10min"),
    "1h": ("60m", "60d", None),
    "4h": ("60m", "120d", "4h"),
    "1d": ("1d", "1y", None),
}


class YFinanceProvider(DataProvider):
    def __init__(self, timeframe: str = "1d"):
        import yfinance  # imported lazily so demo mode never needs it
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {sorted(TIMEFRAMES)}")
        self._yf = yfinance
        self.timeframe = timeframe
        self._tickers: dict[str, object] = {}
        self._info_cache: dict[str, UnderlyingInfo] = {}

    def _ticker(self, ticker: str):
        # Futures roots ("/ES") map to Yahoo continuous contracts ("ES=F")
        # for price history; Yahoo has no futures OPTIONS chains, so those
        # symbols only feed the dips radar unless the tastytrade provider
        # is active.
        from .futures import product_for
        prod = product_for(ticker)
        yahoo = prod.yahoo_symbol if prod else ticker
        if ticker not in self._tickers:
            self._tickers[ticker] = self._yf.Ticker(yahoo)
        return self._tickers[ticker]

    def underlying(self, ticker: str) -> UnderlyingInfo:
        if ticker in self._info_cache:
            return self._info_cache[ticker]
        t = self._ticker(ticker)
        hist = t.history(period="1y", auto_adjust=True, actions=True)
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

        # Realized-vol rank as a stand-in for IV rank when no options-data
        # source is live: where today's 20d HV sits in its 1-year range.
        hv_rank, hv30 = None, None
        try:
            roll = rets.rolling(20).std().dropna() * math.sqrt(TRADING_DAYS)
            if len(roll) >= 40:
                lo, hi = float(roll.min()), float(roll.max())
                hv_rank = (hv20 - lo) / (hi - lo) * 100.0 if hi > lo else 50.0
            last30 = rets.tail(30)
            hv30 = float(last30.std() * math.sqrt(TRADING_DAYS)) if len(last30) > 2 else None
        except Exception:
            pass
        # trailing-12-month dividend yield from the same history call (no
        # extra request); zero for non-payers and futures
        div_yield = 0.0
        try:
            if "Dividends" in hist.columns and spot > 0:
                div_yield = float(hist["Dividends"].sum()) / spot
        except Exception:
            pass

        last_bar = hist.iloc[-1]
        day_high = float(last_bar.get("High", 0) or 0)
        day_low = float(last_bar.get("Low", 0) or 0)

        # RSI / 50-SMA / Bollinger are computed on the scan timeframe: daily
        # bars by default, intraday candles (5m/10m/1h/4h) for scalp mode.
        sig_close = close
        if self.timeframe != "1d":
            try:
                interval, period, resample = TIMEFRAMES[self.timeframe]
                intraday = t.history(period=period, interval=interval, auto_adjust=True)
                if not intraday.empty:
                    sig_close = intraday["Close"]
                    if resample:
                        sig_close = sig_close.resample(resample).last().dropna()
            except Exception:
                pass  # fall back to daily-bar signals

        rsi, sma_50, boll_lower, boll_upper = signal_stats(sig_close.tolist(), spot)

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
                              boll_upper=boll_upper,
                              day_high=day_high, day_low=day_low,
                              iv_rank=hv_rank, hv_30=hv30,
                              dividend_yield=div_yield,
                              iv_source="hv-proxy" if hv_rank is not None else "")
        self._info_cache[ticker] = info
        return info

    def history_lows(self, ticker: str, since: dt.date) -> float | None:
        try:
            hist = self._ticker(ticker).history(start=since.isoformat(), auto_adjust=True)
            if hist.empty or "Low" not in hist.columns:
                return None
            return float(hist["Low"].min())
        except Exception:
            return None

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


def signal_stats(closes: list[float], spot: float) -> tuple[float, float, float, float]:
    """(rsi14, sma50, boll_lower, boll_upper) from a close series on any timeframe.

    Matches TradingView's defaults so the scanner's numbers agree with the
    chart: Wilder-smoothed RSI (fed ~250 bars so the smoothing converges)
    and Bollinger Bands on the population standard deviation."""
    rsi = _rsi(closes[-260:], 14)
    sma_50 = sum(closes[-50:]) / 50.0 if len(closes) >= 50 else spot
    last20 = closes[-20:]
    if len(last20) >= 20:
        mid = sum(last20) / len(last20)
        var = sum((c - mid) ** 2 for c in last20) / len(last20)   # population, as TV
        sd = var ** 0.5
        return rsi, sma_50, mid - 2 * sd, mid + 2 * sd
    return rsi, sma_50, 0.0, 0.0


def _rsi(closes: list[float], period: int = 14) -> float:
    """Wilder's RSI: seed with a simple average of the first `period` moves,
    then smooth recursively with alpha = 1/period (an RMA). This is what
    TradingView, tastytrade and thinkorswim compute; the plain 14-bar
    average (Cutler's RSI) the scanner used before differed by several
    points on the same bar."""
    if len(closes) < period + 1:
        return 50.0
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


# ---------------------------------------------------------------------------
# Synthetic provider (demo mode / tests)
# ---------------------------------------------------------------------------

class SyntheticProvider(DataProvider):
    """Deterministic fake market. Prices options with Black-Scholes off a
    seeded per-ticker spot/vol, so every screen has realistic-looking data."""

    def __init__(self, seed: int = 7, timeframe: str = "1d"):
        self.seed = seed
        self.timeframe = timeframe  # accepted for interface parity; synthetic data ignores it

    def _rng(self, ticker: str) -> random.Random:
        return random.Random(f"{self.seed}:{ticker}")

    def _spot_iv(self, ticker: str) -> tuple[float, float]:
        rng = self._rng(ticker)
        spot = round(rng.uniform(25, 550), 2)
        iv = round(rng.uniform(0.16, 0.65), 3)
        return spot, iv

    @staticmethod
    def _multiplier(ticker: str) -> float:
        from .futures import product_for
        prod = product_for(ticker)
        return prod.multiplier if prod else 100.0

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
            day_high=round(spot * rng.uniform(1.001, 1.03), 2),
            day_low=round(spot * rng.uniform(0.97, 0.999), 2),
            iv_rank=round(rng.uniform(5, 95), 1),
            iv_percentile=round(rng.uniform(5, 95), 1),
            iv_index=iv, hv_30=round(iv * rng.uniform(0.6, 1.0), 3),
            beta=round(rng.uniform(0.4, 1.8), 2),
            dividend_yield=round(rng.choice([0.0, 0.0, 0.015, 0.03, 0.045]), 3),
            liquidity_rating=rng.randint(1, 4), iv_source="synthetic",
        )

    def history_lows(self, ticker: str, since: dt.date) -> float | None:
        # deterministic: the low since any date is 3-9% under spot,
        # seeded per ticker so tests are repeatable
        spot, _ = self._spot_iv(ticker)
        return round(spot * (1.0 - self._rng(ticker + ":low").uniform(0.03, 0.09)), 2)

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
        return ChainSnapshot(ticker, spot, expiry, puts, calls,
                             multiplier=self._multiplier(ticker))


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
