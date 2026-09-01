"""Intraday futures scalp radar.

A separate, fast scan over the handful of futures liquid enough to day
trade. No option chains — this reads intraday candles and answers one
question: is anything washed out (or blown out) enough for a quick
mean-reversion scalp right now?

Setup logic (signals, not hard filters — same philosophy as the income
scanner):

  LONG scalp  — 2 of 3: RSI(14) <= 30 on the scan timeframe,
                price at/below the lower Bollinger Band (20, 2σ),
                price at the session low.
  SHORT scalp — the mirror image at the highs.
  One signal alone = "lean", both sides lit = chop = "no edge".

For an actionable setup the row also carries a trade plan: stop just past
the session extreme (0.6 × ATR beyond it), target back at the 20-bar mean
(the middle of the bands — where mean-reversion scalps pay), and the $
risk per contract from the product multiplier so sizing is one glance.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .data import TIMEFRAMES, _rsi
from .futures import product_for

# The only futures deep enough to scalp with tight fills. /RTY is the
# IWM-equivalent. Micros shown per row for smaller size.
SCALP_FUTURES = ["/ES", "/NQ", "/RTY", "/CL", "/GC", "/SI"]

MICRO_TWIN = {"/ES": "/MES", "/NQ": "/MNQ", "/RTY": "/M2K",
              "/CL": "/MCL", "/GC": "/MGC", "/SI": "/SIL"}

# bars = (high, low, close), oldest first
Bar = tuple[float, float, float]


@dataclass
class ScalpSetup:
    ticker: str
    name: str
    spot: float
    day_low: float
    day_high: float
    range_pos_pct: float | None      # 0 = at the low, 100 = at the high
    rsi: float
    boll_lower: float
    boll_upper: float
    mid_band: float                  # 20-bar mean — the mean-reversion target
    stretch_sigma: float             # (spot − mid) / σ; ±2 = at the bands
    atr: float                       # ATR(14) in points, on the scan timeframe
    per_point: float                 # $ per 1.00 point per contract
    micro: str                       # micro twin symbol for smaller size
    signals: frozenset = frozenset()
    bias: str = "no edge"            # LONG SCALP / SHORT SCALP / lean long / lean short / no edge
    stop: float | None = None
    target: float | None = None
    risk_dollars: float | None = None    # (entry − stop) × per_point
    reward_dollars: float | None = None  # (target − entry) × per_point


def _atr(bars: list[Bar], period: int = 14) -> float:
    """Average true range over the last `period` bars."""
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h, l, _ = bars[i]
        prev_close = bars[i - 1][2]
        trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
    recent = trs[-period:]
    return sum(recent) / len(recent)


def analyze(ticker: str, bars: list[Bar], spot: float,
            day_low: float = 0.0, day_high: float = 0.0) -> ScalpSetup:
    """Classify one product from its intraday bars. Pure — no I/O."""
    if len(bars) < 21:
        raise ValueError(f"{ticker}: need >=21 intraday bars, got {len(bars)}")
    closes = [c for _, _, c in bars]
    spot = spot or closes[-1]
    rsi = _rsi(closes[-60:], 14)

    last20 = closes[-20:]
    mid = sum(last20) / len(last20)
    var = sum((c - mid) ** 2 for c in last20) / (len(last20) - 1)
    sd = var ** 0.5
    lower, upper = mid - 2 * sd, mid + 2 * sd
    stretch = (spot - mid) / sd if sd > 0 else 0.0
    atr = _atr(bars)

    range_pos = None
    if day_high > day_low > 0:
        range_pos = max(0.0, min(100.0, (spot - day_low) / (day_high - day_low) * 100.0))

    at_low = (day_low > 0 and spot <= day_low * 1.0015) or \
             (range_pos is not None and range_pos <= 10.0)
    at_high = (day_high > 0 and spot >= day_high * 0.9985) or \
              (range_pos is not None and range_pos >= 90.0)

    # σ = 0 means a dead-flat tape: nothing to mean-revert, and the RSI
    # helper degenerates (returns 100 with zero losses) — no signals at all.
    long_sigs, short_sigs = set(), set()
    if sd > 0:
        if rsi <= 30:
            long_sigs.add("RSI<=30")
        if rsi >= 70:
            short_sigs.add("RSI>=70")
        if spot <= lower:
            long_sigs.add("<lower BB")
        if spot >= upper:
            short_sigs.add(">upper BB")
        if at_low:
            long_sigs.add("at day low")
        if at_high:
            short_sigs.add("at day high")

    n_l, n_s = len(long_sigs), len(short_sigs)
    if n_l >= 2 and n_l > n_s:
        bias = "LONG SCALP"
    elif n_s >= 2 and n_s > n_l:
        bias = "SHORT SCALP"
    elif n_l == 1 and n_s == 0:
        bias = "lean long"
    elif n_s == 1 and n_l == 0:
        bias = "lean short"
    else:
        bias = "no edge"

    prod = product_for(ticker)
    per_point = prod.multiplier if prod else 1.0

    stop = target = risk = reward = None
    if atr > 0 and bias in ("LONG SCALP", "lean long"):
        anchor = min(spot, day_low) if day_low > 0 else spot
        stop = anchor - 0.6 * atr
        target = mid
        risk = (spot - stop) * per_point
        reward = max(target - spot, 0.0) * per_point
    elif atr > 0 and bias in ("SHORT SCALP", "lean short"):
        anchor = max(spot, day_high) if day_high > 0 else spot
        stop = anchor + 0.6 * atr
        target = mid
        risk = (stop - spot) * per_point
        reward = max(spot - target, 0.0) * per_point

    return ScalpSetup(
        ticker=ticker, name=prod.name if prod else ticker, spot=spot,
        day_low=day_low, day_high=day_high, range_pos_pct=range_pos,
        rsi=rsi, boll_lower=lower, boll_upper=upper, mid_band=mid,
        stretch_sigma=stretch, atr=atr, per_point=per_point,
        micro=MICRO_TWIN.get(ticker, ""), signals=frozenset(long_sigs | short_sigs),
        bias=bias, stop=stop, target=target,
        risk_dollars=risk, reward_dollars=reward)


# ---------------------------------------------------------------------------
# Snapshot sources: (bars, spot, day_low, day_high) per ticker
# ---------------------------------------------------------------------------

def yahoo_snapshot(ticker: str, timeframe: str) -> tuple[list[Bar], float, float, float]:
    """Delayed intraday bars from Yahoo (fallback when tastytrade is off)."""
    import yfinance
    prod = product_for(ticker)
    ysym = prod.yahoo_symbol if prod else ticker
    interval, period, resample = TIMEFRAMES[timeframe]
    t = yfinance.Ticker(ysym)
    hist = t.history(period=period, interval=interval, auto_adjust=True)
    if hist.empty:
        raise ValueError(f"no intraday history for {ticker}")
    if resample:
        hist = hist.resample(resample).agg(
            {"High": "max", "Low": "min", "Close": "last"}).dropna()
    bars = [(float(h), float(l), float(c)) for h, l, c in
            zip(hist["High"], hist["Low"], hist["Close"])]
    spot = bars[-1][2]
    # today's session extremes from the current daily bar
    day_low = day_high = 0.0
    try:
        daily = t.history(period="2d", interval="1d", auto_adjust=True)
        if not daily.empty:
            day_high = float(daily["High"].iloc[-1])
            day_low = float(daily["Low"].iloc[-1])
    except Exception:
        pass
    return bars, spot, day_low, day_high


def demo_snapshot(ticker: str, timeframe: str = "5m",
                  seed: int = 7) -> tuple[list[Bar], float, float, float]:
    """Deterministic synthetic bars for demo mode and tests."""
    import random
    rng = random.Random(f"{seed}:{ticker}:{timeframe}")
    base = {"/ES": 7650.0, "/NQ": 29100.0, "/RTY": 2450.0,
            "/CL": 88.0, "/GC": 4410.0, "/SI": 55.0}.get(ticker, 100.0)
    price, bars = base, []
    for _ in range(80):
        drift = rng.gauss(0, base * 0.0012)
        o, c = price, price + drift
        h = max(o, c) + abs(rng.gauss(0, base * 0.0005))
        l = min(o, c) - abs(rng.gauss(0, base * 0.0005))
        bars.append((h, l, c))
        price = c
    spot = bars[-1][2]
    day = bars[-30:]
    return bars, spot, min(l for _, l, _ in day), max(h for h, _, _ in day)


def run_scalp_scan(timeframe: str, tickers: list[str] | None = None,
                   source: str = "tasty", session=None,
                   progress=None) -> tuple[list[ScalpSetup], dict[str, str]]:
    """Sweep the scalp universe. source: 'tasty' | 'yahoo' | 'demo'."""
    tickers = tickers or SCALP_FUTURES
    rows, errors = [], {}

    tasty = None
    if source == "tasty":
        from .tastytrade_provider import TastytradeProvider
        tasty = TastytradeProvider(session=session, timeframe=timeframe)

    for i, tk in enumerate(tickers):
        if progress:
            progress(i, len(tickers), tk)
        try:
            if source == "demo":
                bars, spot, lo, hi = demo_snapshot(tk, timeframe)
            elif source == "tasty":
                bars, spot, lo, hi = tasty.scalp_snapshot(tk)
                if len(bars) < 21:  # streamer hiccup — degrade to delayed data
                    bars, spot2, lo2, hi2 = yahoo_snapshot(tk, timeframe)
                    spot, lo, hi = spot or spot2, lo or lo2, hi or hi2
            else:
                bars, spot, lo, hi = yahoo_snapshot(tk, timeframe)
            rows.append(analyze(tk, bars, spot, lo, hi))
        except Exception as exc:  # one dead feed must not kill the radar
            errors[tk] = str(exc)

    order = {"LONG SCALP": 0, "SHORT SCALP": 0, "lean long": 1, "lean short": 1}
    rows.sort(key=lambda r: (order.get(r.bias, 2), -abs(r.stretch_sigma)))
    return rows, errors
