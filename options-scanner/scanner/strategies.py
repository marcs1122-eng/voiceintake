"""Strategy construction and metrics.

Everything is computed off mid prices; fills near mid are realistic on the
liquid names this scanner filters for, but always work your own limit price.
Premiums are per share (multiply by 100 for per-contract dollars).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import bs
from .data import ChainSnapshot, OptionQuote


def _annualize(roc: float, dte: int) -> float:
    return roc * 365.0 / max(dte, 1)


def _t_years(dte: int) -> float:
    return max(dte, 1) / 365.0


# ---------------------------------------------------------------------------
# Cash-secured put (the wheel entry)
# ---------------------------------------------------------------------------

@dataclass
class CashSecuredPut:
    ticker: str
    spot: float
    expiry: dt.date
    dte: int
    strike: float
    bid: float
    mid: float
    iv: float
    delta: float               # put delta, negative
    open_interest: int
    volume: int
    spread_pct: float
    earnings_before_expiry: bool
    entry_signals: frozenset = frozenset()   # e.g. {"RSI<=30", "LowerBB", "50SMA"}
    multiplier: float = 100.0                # $ per 1.00 of premium
    margin_estimate: float | None = None     # futures: initial margin per contract
    rsi_14: float = 50.0                     # underlying's RSI on the scan timeframe
    expected_move: float | None = None       # 1σ move to expiry, price units
    iv_rank: float | None = None             # 0-100 (tastytrade) or HV-rank proxy
    dividend_yield: float = 0.0

    @property
    def is_futures(self) -> bool:
        return self.margin_estimate is not None

    @property
    def em_cushion(self) -> float | None:
        """How many expected moves the strike sits below spot. ≥ 1.0 is the
        professional's 'outside one expected move'."""
        if not self.expected_move:
            return None
        return (self.spot - self.strike) / self.expected_move

    @property
    def capital(self) -> float:
        """Capital to hold one contract: full cash for a stock/ETF CSP,
        initial-margin estimate for a futures short put."""
        if self.margin_estimate is not None:
            return self.margin_estimate
        return self.strike * self.multiplier

    @property
    def premium(self) -> float:
        """Credit per contract at mid."""
        return self.mid * self.multiplier

    @property
    def roc_pct(self) -> float:
        """Return on capital for the trade period, %."""
        return self.premium / self.capital * 100.0

    @property
    def annualized_pct(self) -> float:
        return _annualize(self.roc_pct, self.dte)

    @property
    def breakeven(self) -> float:
        return self.strike - self.mid

    @property
    def downside_protection_pct(self) -> float:
        """How far the stock can fall before you lose money at expiry."""
        return (1.0 - self.breakeven / self.spot) * 100.0

    @property
    def otm_pct(self) -> float:
        return (1.0 - self.strike / self.spot) * 100.0

    @property
    def prob_otm_pct(self) -> float:
        """P(expires worthless) ≈ 1 - |delta|."""
        return (1.0 + self.delta) * 100.0


def build_csps(chain: ChainSnapshot, *, min_dte_ok: bool = True,
               earnings_before_expiry: bool = False,
               delta_range: tuple[float, float] = (0.10, 0.40),
               min_open_interest: int = 100,
               max_spread_pct: float = 0.25,
               min_premium: float = 0.05,
               entry_signals: frozenset = frozenset(),
               margin_estimate: float | None = None,
               rsi_14: float = 50.0,
               expected_move: float | None = None,
               iv_rank: float | None = None,
               dividend_yield: float = 0.0) -> list[CashSecuredPut]:
    """All OTM puts in the chain that pass liquidity/delta filters."""
    out = []
    t = _t_years(chain.dte)
    for q in chain.puts:
        if q.strike >= chain.spot:            # OTM puts only
            continue
        # min_premium is quoted per-share equity-style ($0.10 = $10/contract);
        # compare in dollars so futures multipliers don't skew the filter
        if q.mid * chain.multiplier < min_premium * 100.0 or q.iv <= 0:
            continue
        if q.open_interest < min_open_interest:
            continue
        if q.spread_pct > max_spread_pct:
            continue
        try:
            delta = bs.put_delta(chain.spot, q.strike, q.iv, t, q=dividend_yield)
        except ValueError:
            continue
        if not (delta_range[0] <= abs(delta) <= delta_range[1]):
            continue
        out.append(CashSecuredPut(
            ticker=chain.ticker, spot=chain.spot, expiry=chain.expiry,
            dte=chain.dte, strike=q.strike, bid=q.bid, mid=round(q.mid, 2),
            iv=q.iv, delta=delta, open_interest=q.open_interest,
            volume=q.volume, spread_pct=q.spread_pct,
            earnings_before_expiry=earnings_before_expiry,
            entry_signals=entry_signals,
            multiplier=chain.multiplier, margin_estimate=margin_estimate,
            rsi_14=rsi_14, expected_move=expected_move, iv_rank=iv_rank,
            dividend_yield=dividend_yield,
        ))
    return out


# ---------------------------------------------------------------------------
# Iron condor
# ---------------------------------------------------------------------------

@dataclass
class IronCondor:
    ticker: str
    spot: float
    expiry: dt.date
    dte: int
    put_long: float
    put_short: float
    call_short: float
    call_long: float
    credit: float              # per share, at mid
    put_short_delta: float
    call_short_delta: float
    min_open_interest: int
    earnings_before_expiry: bool
    iv_atm: float
    multiplier: float = 100.0

    @property
    def width(self) -> float:
        return max(self.put_short - self.put_long, self.call_long - self.call_short)

    @property
    def max_loss(self) -> float:
        """Per share."""
        return self.width - self.credit

    @property
    def max_loss_dollars(self) -> float:
        return self.max_loss * self.multiplier

    @property
    def credit_dollars(self) -> float:
        return self.credit * self.multiplier

    @property
    def roc_pct(self) -> float:
        return self.credit / self.max_loss * 100.0 if self.max_loss > 0 else float("inf")

    @property
    def annualized_pct(self) -> float:
        return _annualize(self.roc_pct, self.dte)

    @property
    def breakeven_low(self) -> float:
        return self.put_short - self.credit

    @property
    def breakeven_high(self) -> float:
        return self.call_short + self.credit

    @property
    def pop_pct(self) -> float:
        """P(finishes between breakevens), lognormal estimate at ATM IV."""
        t = _t_years(self.dte)
        p_below = bs.prob_below(self.spot, self.breakeven_low, self.iv_atm, t)
        p_above = bs.prob_above(self.spot, self.breakeven_high, self.iv_atm, t)
        return max(0.0, (1.0 - p_below - p_above)) * 100.0


def build_iron_condor(chain: ChainSnapshot, *, short_delta: float = 0.16,
                      width_pct: float = 0.02, min_open_interest: int = 100,
                      earnings_before_expiry: bool = False) -> IronCondor | None:
    """Short strikes nearest the target delta, long wings ~width_pct of spot away."""
    t = _t_years(chain.dte)
    spot = chain.spot

    def liquid(quotes: list[OptionQuote]) -> list[OptionQuote]:
        return [q for q in quotes if q.iv > 0 and q.mid > 0
                and q.open_interest >= min_open_interest]

    puts, calls = liquid(chain.puts), liquid(chain.calls)
    otm_puts = [q for q in puts if q.strike < spot]
    otm_calls = [q for q in calls if q.strike > spot]
    if len(otm_puts) < 2 or len(otm_calls) < 2:
        return None

    ps = min(otm_puts, key=lambda q: abs(abs(bs.put_delta(spot, q.strike, q.iv, t)) - short_delta))
    cs = min(otm_calls, key=lambda q: abs(bs.call_delta(spot, q.strike, q.iv, t) - short_delta))

    width = max(spot * width_pct, 1.0)
    pl_candidates = [q for q in puts if q.strike < ps.strike]
    cl_candidates = [q for q in calls if q.strike > cs.strike]
    if not pl_candidates or not cl_candidates:
        return None
    pl = min(pl_candidates, key=lambda q: abs((ps.strike - q.strike) - width))
    cl = min(cl_candidates, key=lambda q: abs((q.strike - cs.strike) - width))

    credit = ps.mid - pl.mid + cs.mid - cl.mid
    if credit <= 0:
        return None

    atm = min(puts, key=lambda q: abs(q.strike - spot))
    return IronCondor(
        ticker=chain.ticker, spot=spot, expiry=chain.expiry, dte=chain.dte,
        put_long=pl.strike, put_short=ps.strike,
        call_short=cs.strike, call_long=cl.strike,
        credit=round(credit, 2),
        put_short_delta=bs.put_delta(spot, ps.strike, ps.iv, t),
        call_short_delta=bs.call_delta(spot, cs.strike, cs.iv, t),
        min_open_interest=min(ps.open_interest, cs.open_interest,
                              pl.open_interest, cl.open_interest),
        earnings_before_expiry=earnings_before_expiry, iv_atm=atm.iv,
        multiplier=chain.multiplier,
    )


# ---------------------------------------------------------------------------
# Broken wing (put) butterfly — skip-strike fly with no upside risk if
# placed for a credit.
# ---------------------------------------------------------------------------

@dataclass
class BrokenWingButterfly:
    ticker: str
    spot: float
    expiry: dt.date
    dte: int
    long_low: float            # K1 (farthest OTM)
    short_mid: float           # K2 (x2 short)
    long_high: float           # K3 (closest to money)
    net_credit: float          # per share; negative = debit
    body_delta: float
    min_open_interest: int
    earnings_before_expiry: bool
    iv_atm: float
    multiplier: float = 100.0

    @property
    def credit_dollars(self) -> float:
        """Net credit per contract (negative = debit)."""
        return self.net_credit * self.multiplier

    @property
    def max_profit_dollars(self) -> float:
        return self.max_profit * self.multiplier

    @property
    def max_loss_dollars(self) -> float:
        return max(self.max_loss, 0.0) * self.multiplier

    @property
    def upper_width(self) -> float:
        return self.long_high - self.short_mid

    @property
    def lower_width(self) -> float:
        return self.short_mid - self.long_low

    @property
    def max_profit(self) -> float:
        """Per share, with underlying pinned at the short strike."""
        return self.upper_width + self.net_credit

    @property
    def max_loss(self) -> float:
        """Per share, underlying below the low wing. Zero/negative means no
        risk beyond commissions (rare; requires huge skew)."""
        return (self.lower_width - self.upper_width) - self.net_credit

    @property
    def upside_risk(self) -> bool:
        """True if the fly loses money when price runs UP (i.e., entered for a debit)."""
        return self.net_credit < 0

    @property
    def breakeven_low(self) -> float:
        # Between K1 and K2 payoff = (K3 - 2*K2 + S) + credit
        return 2 * self.short_mid - self.long_high - self.net_credit

    @property
    def roc_pct(self) -> float:
        ml = self.max_loss
        return self.max_profit / ml * 100.0 if ml > 0 else float("inf")

    @property
    def pop_pct(self) -> float:
        """P(above lower breakeven). With a credit there's no upside loss,
        so this is the full probability of profit."""
        t = _t_years(self.dte)
        return bs.prob_above(self.spot, self.breakeven_low, self.iv_atm, t) * 100.0


def build_bwb(chain: ChainSnapshot, *, body_delta: float = 0.30,
              upper_width_pct: float = 0.025, skip_ratio: float = 2.0,
              min_open_interest: int = 50,
              earnings_before_expiry: bool = False) -> BrokenWingButterfly | None:
    """Put BWB below the market: sell 2x at ~body_delta, buy a narrow wing
    above (toward the money) and a wing ~skip_ratio× wider below."""
    t = _t_years(chain.dte)
    spot = chain.spot
    puts = [q for q in chain.puts if q.iv > 0 and q.mid > 0
            and q.open_interest >= min_open_interest and q.strike < spot]
    if len(puts) < 3:
        return None

    upper_width = max(spot * upper_width_pct, 1.0)

    # Try bodies nearest the target delta first; fall back to the next-best
    # strike when the closest one leaves no room for a wing on either side.
    bodies = sorted(puts, key=lambda q: abs(abs(bs.put_delta(spot, q.strike, q.iv, t)) - body_delta))
    body = k1 = k3 = None
    for cand in bodies:
        highs = [q for q in puts if q.strike > cand.strike]
        lows = [q for q in puts if q.strike < cand.strike]
        if not highs or not lows:
            continue
        c3 = min(highs, key=lambda q: abs((q.strike - cand.strike) - upper_width))
        lower_target = (c3.strike - cand.strike) * skip_ratio
        c1 = min(lows, key=lambda q: abs((cand.strike - q.strike) - lower_target))
        if (cand.strike - c1.strike) > (c3.strike - cand.strike):  # wing actually broken
            body, k1, k3 = cand, c1, c3
            break
    if body is None:
        return None

    net_credit = 2 * body.mid - k1.mid - k3.mid
    atm = min(chain.puts, key=lambda q: abs(q.strike - spot))
    return BrokenWingButterfly(
        ticker=chain.ticker, spot=spot, expiry=chain.expiry, dte=chain.dte,
        long_low=k1.strike, short_mid=body.strike, long_high=k3.strike,
        net_credit=round(net_credit, 2),
        body_delta=bs.put_delta(spot, body.strike, body.iv, t),
        min_open_interest=min(k1.open_interest, body.open_interest, k3.open_interest),
        earnings_before_expiry=earnings_before_expiry, iv_atm=atm.iv,
        multiplier=chain.multiplier,
    )


# ---------------------------------------------------------------------------
# Credit spreads — the defined-risk version of the put sale (and the only
# way Mac sells calls)
# ---------------------------------------------------------------------------

@dataclass
class CreditSpread:
    ticker: str
    spot: float
    expiry: dt.date
    dte: int
    side: str                  # "put" (bull put spread) | "call" (bear call spread)
    short_strike: float
    long_strike: float
    credit: float              # per share, at mid (short mid − long mid)
    short_delta: float         # absolute
    short_iv: float
    min_open_interest: int
    earnings_before_expiry: bool
    multiplier: float = 100.0
    iv_rank: float | None = None
    rsi_14: float = 0.0
    entry_signals: frozenset = frozenset()
    at_upper: bool = False     # spot at/through the upper band (call-spread tailwind)

    @property
    def width(self) -> float:
        return abs(self.short_strike - self.long_strike)

    @property
    def max_loss(self) -> float:
        return max(self.width - self.credit, 0.0)

    @property
    def credit_dollars(self) -> float:
        return self.credit * self.multiplier

    @property
    def max_loss_dollars(self) -> float:
        return self.max_loss * self.multiplier

    @property
    def credit_to_width(self) -> float:
        return self.credit / self.width if self.width > 0 else 0.0

    @property
    def roc_pct(self) -> float:
        return self.credit / self.max_loss * 100.0 if self.max_loss > 0 else float("inf")

    @property
    def annualized_pct(self) -> float:
        return _annualize(min(self.roc_pct, 1000.0), self.dte)

    @property
    def breakeven(self) -> float:
        return self.short_strike - self.credit if self.side == "put" else self.short_strike + self.credit

    @property
    def prob_otm_pct(self) -> float:
        """P(short strike finishes out of the money), lognormal at the short strike's IV."""
        t = _t_years(self.dte)
        if self.side == "put":
            return bs.prob_above(self.spot, self.short_strike, self.short_iv, t) * 100.0
        return bs.prob_below(self.spot, self.short_strike, self.short_iv, t) * 100.0

    @property
    def is_futures(self) -> bool:
        return self.ticker.startswith("/")

    @property
    def legs(self) -> str:
        if self.side == "put":
            return f"{self.long_strike:g}/{self.short_strike:g} put credit spread"
        return f"{self.short_strike:g}/{self.long_strike:g} call credit spread"


def build_credit_spreads(chain: ChainSnapshot, *, delta_range: tuple[float, float] = (0.20, 0.30),
                         width_pct: float = 0.025, min_open_interest: int = 100,
                         earnings_before_expiry: bool = False, iv_rank: float | None = None,
                         rsi_14: float = 0.0, entry_signals: frozenset = frozenset(),
                         at_upper: bool = False, sides: tuple[str, ...] = ("put", "call"),
                         dividend_yield: float = 0.0) -> list[CreditSpread]:
    """One spread per side: short strike nearest the middle of the delta band,
    long strike the first one at least width_pct of spot further out."""
    t = _t_years(chain.dte)
    spot = chain.spot
    target = (delta_range[0] + delta_range[1]) / 2.0
    min_width = max(spot * width_pct, 0.5)
    out: list[CreditSpread] = []
    for side in sides:
        quotes = [q for q in (chain.puts if side == "put" else chain.calls)
                  if q.iv > 0 and q.mid > 0 and q.open_interest >= min_open_interest]
        otm = [q for q in quotes if (q.strike < spot if side == "put" else q.strike > spot)]
        if len(otm) < 2:
            continue
        cands = []
        for q in otm:
            try:
                d = abs((bs.put_delta if side == "put" else bs.call_delta)(spot, q.strike, q.iv, t, q=dividend_yield))
            except ValueError:
                continue
            cands.append((abs(d - target), d, q))
        in_band = [c for c in cands if delta_range[0] <= c[1] <= delta_range[1]]
        # coarse strike grids (5-point strikes on a $100 stock) can skip the band
        # entirely; fall back to the nearest strike within 0.10 of the band edges
        pool = in_band or [c for c in cands if delta_range[0] - 0.10 <= c[1] <= delta_range[1] + 0.10]
        if not pool:
            continue
        _, d, short = min(pool, key=lambda x: x[0])
        if side == "put":
            wings = sorted((q for q in otm if q.strike <= short.strike - min_width), key=lambda q: -q.strike)
        else:
            wings = sorted((q for q in otm if q.strike >= short.strike + min_width), key=lambda q: q.strike)
        if not wings:
            continue
        long = wings[0]
        credit = short.mid - long.mid
        if credit <= 0:
            continue
        out.append(CreditSpread(
            ticker=chain.ticker, spot=spot, expiry=chain.expiry, dte=chain.dte, side=side,
            short_strike=short.strike, long_strike=long.strike, credit=round(credit, 2),
            short_delta=round(d, 3), short_iv=short.iv,
            min_open_interest=min(short.open_interest, long.open_interest),
            earnings_before_expiry=earnings_before_expiry, multiplier=chain.multiplier,
            iv_rank=iv_rank, rsi_14=rsi_14, entry_signals=entry_signals, at_upper=at_upper))
    return out
