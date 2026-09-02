"""Roll assistant — what to do with a short option that is being tested.

For a short strike under pressure the two standard repairs are: roll the
same strike out in time for a credit, or roll one strike further out of
the money (down for puts, up for calls) and out in time. This fetches the
next few expirations and prices both, so the decision is a table instead
of six chain lookups.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import bs
from .data import DataProvider


@dataclass
class RollOption:
    label: str            # "same strike" | "one strike out"
    expiry: dt.date
    dte: int
    strike: float
    new_mid: float        # per share, what the new short sells for
    net: float            # per share: new_mid - cost to close; + = credit
    multiplier: float
    delta: float
    new_breakeven: float  # after all credits collected
    open_interest: int

    @property
    def net_dollars(self) -> float:
        return self.net * self.multiplier

    @property
    def is_credit(self) -> bool:
        return self.net > 0


def roll_candidates(provider: DataProvider, ticker: str, strike: float, is_put: bool,
                    current_expiry: dt.date, current_mark: float,
                    original_credit: float = 0.0,
                    min_days_out: int = 14, max_days_out: int = 60,
                    max_expiries: int = 3) -> list[RollOption]:
    """Price the standard rolls for a short option.

    current_mark     — what it costs to buy the existing short back (per share)
    original_credit  — what it was sold for (per share); used for the new
                       breakeven, which is strike minus every credit collected
    """
    info = provider.underlying(ticker)
    exps = sorted(e for e in info.expiries
                  if min_days_out <= (e - current_expiry).days <= max_days_out)[:max_expiries]
    out: list[RollOption] = []
    for e in exps:
        try:
            chain = provider.chain(ticker, e)
        except Exception:
            continue
        quotes = [q for q in (chain.puts if is_put else chain.calls) if q.mid > 0 and q.iv > 0]
        if not quotes:
            continue
        by_strike = {q.strike: q for q in quotes}
        same = by_strike.get(strike)
        if is_put:
            further = [q for q in quotes if q.strike < strike]
            further = max(further, key=lambda q: q.strike) if further else None
        else:
            further = [q for q in quotes if q.strike > strike]
            further = min(further, key=lambda q: q.strike) if further else None
        t = max(chain.dte, 1) / 365.0
        for label, q in (("same strike", same), ("one strike out", further)):
            if q is None:
                continue
            net = q.mid - current_mark
            try:
                d = (bs.put_delta if is_put else bs.call_delta)(chain.spot, q.strike, q.iv, t)
            except ValueError:
                d = 0.0
            total_credit = original_credit + net
            be = q.strike - total_credit if is_put else q.strike + total_credit
            out.append(RollOption(label=label, expiry=e, dte=chain.dte, strike=q.strike,
                                  new_mid=round(q.mid, 2), net=round(net, 2),
                                  multiplier=chain.multiplier, delta=d,
                                  new_breakeven=round(be, 2), open_interest=q.open_interest))
    # best first: credits before debits, then the biggest credit
    out.sort(key=lambda r: (not r.is_credit, -r.net))
    return out


def best_roll(rolls: list[RollOption]) -> RollOption | None:
    """The roll a premium seller takes by default: the largest credit; a
    debit roll is only shown, never recommended."""
    credits = [r for r in rolls if r.is_credit]
    return credits[0] if credits else None
