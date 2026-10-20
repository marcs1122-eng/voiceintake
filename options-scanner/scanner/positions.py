"""Positions as *structures*, not legs.

tastytrade hands back one row per leg. A short strangle is two rows, and
judging each leg on its own mark gives nonsense: the put side of a
strangle shows "losing" while the whole trade sits inside the tent. This
module groups legs into the structure that was actually sold, works out
the total credit and the real breakevens, and makes the management call
the way a premium seller would:

  * CLOSE          — the ladder hit (25% day one, 30% day two, then 50%)
  * ROLL FORWARD   — 25%+ captured: take it and re-sell further out to add time
  * TESTED         — spot is through a short strike; for a strangle, roll the
                     *untested* side in toward its original delta for credit
  * BREACHED       — spot is past the structure's breakeven; defend or take it
  * WINDOW         — inside 21 DTE, roll or close even if healthy
  * hold

Spot prices come from the caller (a provider's batch quote); without a
spot the call falls back to the mark, clearly labelled as such.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

from .rules import is_option_row, parse_option

STATUS_ORDER = {"breached": 0, "tested": 1, "close": 2, "roll_forward": 3,
                "window": 4, "hold": 5, "": 6}


@dataclass
class Structure:
    account: str
    underlying: str
    expires: str                 # MM/DD/YYYY as the rows carry it
    dte: int | None
    kind: str                    # short put | short call | strangle | straddle | put spread | call spread | iron condor | long ... | mixed
    legs: list[dict] = field(default_factory=list)
    qty: float = 1.0             # number of structures (min short-leg quantity)
    multiplier: float = 100.0
    credit: float = 0.0          # per share, net of long legs, for one structure
    mark_total: float = 0.0      # per share, what it costs to close one structure now
    pl_open: float = 0.0
    days_held: int | None = None
    short_put: float | None = None
    short_call: float | None = None
    long_put: float | None = None
    long_call: float | None = None
    spot: float | None = None
    status: str = ""
    suggestion: str = ""

    # -- derived -----------------------------------------------------------
    @property
    def is_short_premium(self) -> bool:
        return self.credit > 0 and (self.short_put is not None or self.short_call is not None)

    @property
    def pct_of_max(self) -> float | None:
        if not self.is_short_premium or self.credit <= 0:
            return None
        return (1.0 - self.mark_total / self.credit) * 100.0

    @property
    def breakeven_low(self) -> float | None:
        return round(self.short_put - self.credit, 2) if self.short_put is not None else None

    @property
    def breakeven_high(self) -> float | None:
        return round(self.short_call + self.credit, 2) if self.short_call is not None else None

    @property
    def display(self) -> str:
        k = self.kind
        if k == "strangle":
            body = f"{self.short_put:g}P / {self.short_call:g}C strangle"
        elif k == "straddle":
            body = f"{self.short_put:g} straddle"
        elif k == "short put":
            body = f"{self.short_put:g} put"
        elif k == "short call":
            body = f"{self.short_call:g} call"
        elif k == "put spread":
            body = f"{self.long_put:g}/{self.short_put:g} put spread"
        elif k == "call spread":
            body = f"{self.short_call:g}/{self.long_call:g} call spread"
        elif k == "iron condor":
            body = f"{self.long_put:g}/{self.short_put:g}P {self.short_call:g}/{self.long_call:g}C condor"
        else:
            body = f"{len(self.legs)}-leg {k}"
        q = f" ×{self.qty:g}" if self.qty != 1 else ""
        return f"{self.underlying} {self.expires[:5]}/{self.expires[-2:]} {body}{q}"

    @property
    def icon(self) -> str:
        return {"breached": "🔴", "tested": "⚠️", "close": "💰", "roll_forward": "📈",
                "window": "⏰", "hold": "🟢"}.get(self.status, "")


def _sign(r: dict) -> float:
    return -1.0 if str(r.get("direction", "")).upper().startswith("SHORT") else 1.0


def group(rows: list[dict]) -> list[Structure]:
    """Legs → structures, keyed on account + underlying + expiry."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if not is_option_row(r):
            continue
        po = parse_option(r.get("symbol", ""))
        if not po:
            continue
        leg = dict(r)
        leg.update(strike=po["strike"], is_put=po["is_put"], _sign=_sign(r))
        buckets[(r.get("account", ""), r.get("underlying", ""), r.get("expires", ""))].append(leg)

    out: list[Structure] = []
    for (acct, under, exp), legs in buckets.items():
        s = Structure(account=acct, underlying=under, expires=exp,
                      dte=min((l.get("dte") for l in legs if l.get("dte") is not None), default=None),
                      kind="", legs=legs)
        shorts = [l for l in legs if l["_sign"] < 0]
        longs = [l for l in legs if l["_sign"] > 0]
        base = min((abs(float(l.get("qty", 1))) for l in shorts), default=None) \
            or min((abs(float(l.get("qty", 1))) for l in legs), default=1.0)
        s.qty = base or 1.0
        s.multiplier = _multiplier(under, legs)
        for l in legs:
            ratio = abs(float(l.get("qty", 1))) / s.qty
            op, mk = float(l.get("open_price") or 0), float(l.get("mark") or 0)
            if l["_sign"] < 0:
                s.credit += op * ratio
                s.mark_total += mk * ratio
            else:
                s.credit -= op * ratio
                s.mark_total -= mk * ratio
            s.pl_open += float(l.get("pl_open") or 0)
        held = [l.get("days_held") for l in legs if l.get("days_held") is not None]
        s.days_held = min(held) if held else None

        sp = [l["strike"] for l in shorts if l["is_put"]]
        sc = [l["strike"] for l in shorts if not l["is_put"]]
        lp = [l["strike"] for l in longs if l["is_put"]]
        lc = [l["strike"] for l in longs if not l["is_put"]]
        s.short_put = max(sp) if sp else None      # the short put nearest the money
        s.short_call = min(sc) if sc else None
        s.long_put = max(lp) if lp else None
        s.long_call = min(lc) if lc else None
        s.kind = _classify(s, shorts, longs)
        out.append(s)
    return out


def _multiplier(under: str, legs: list[dict]) -> float:
    for l in legs:
        m = l.get("multiplier")
        if m:
            return float(m)
    if under.startswith("/"):
        try:
            from .futures import product_for
            from .rules import futures_root
            p = product_for(under) or product_for(futures_root(under))
            if p:
                return float(p.multiplier)
        except Exception:
            pass
    return 100.0


def _classify(s: Structure, shorts: list[dict], longs: list[dict]) -> str:
    ns, nl = len(shorts), len(longs)
    if ns == 2 and nl == 2 and s.short_put and s.short_call and s.long_put and s.long_call:
        return "iron condor"
    if ns == 2 and nl == 0 and s.short_put is not None and s.short_call is not None:
        return "straddle" if s.short_put == s.short_call else "strangle"
    if ns == 1 and nl == 1:
        if s.short_put is not None and s.long_put is not None:
            return "put spread"
        if s.short_call is not None and s.long_call is not None:
            return "call spread"
    if ns == 1 and nl == 0:
        return "short put" if s.short_put is not None else "short call"
    if ns == 0 and nl >= 1:
        return "long put" if s.long_put is not None and s.long_call is None else (
            "long call" if s.long_call is not None and s.long_put is None else "long combo")
    return "mixed"


# ---------------------------------------------------------------------------
# the management call
# ---------------------------------------------------------------------------

def _ladder_target(days_held: int | None) -> tuple[float, str]:
    if days_held == 0:
        return 25.0, "day-1 rule (25%)"
    if days_held == 1:
        return 30.0, "day-2 rule (30%)"
    return 50.0, "50% rule"


def suggest(s: Structure, spot: float | None = None, roll_forward_pct: float = 25.0,
            window_dte: int = 21, target_delta: float = 0.25) -> Structure:
    """Fill status + suggestion on the structure. Order of precedence:
    breached > tested > close > roll forward > window > hold."""
    s.spot = spot
    if not s.is_short_premium:
        s.status, s.suggestion = "", ""
        return s
    pct = s.pct_of_max or 0.0
    cr = s.credit
    m = s.multiplier
    be_lo, be_hi = s.breakeven_low, s.breakeven_high
    tent = ""
    if s.kind in ("strangle", "straddle", "iron condor"):
        tent = f"breakevens {be_lo:g}–{be_hi:g} on {cr:.2f} total credit"
    elif be_lo is not None:
        tent = f"breakeven {be_lo:g} on {cr:.2f} credit"
    elif be_hi is not None:
        tent = f"breakeven {be_hi:g} on {cr:.2f} credit"

    # -- price-based tests need a spot --
    if spot:
        if be_lo is not None and spot < be_lo:
            s.status = "breached"
            s.suggestion = (f"🔴 BREACHED — {spot:g} is below the breakeven {be_lo:g}. "
                            f"Roll the put down & out for a credit, or take the loss.")
            return s
        if be_hi is not None and spot > be_hi:
            s.status = "breached"
            s.suggestion = (f"🔴 BREACHED — {spot:g} is above the breakeven {be_hi:g}. "
                            f"Roll the call up & out for a credit, or take the loss.")
            return s
        if s.short_put is not None and spot <= s.short_put:
            s.status = "tested"
            if s.kind in ("strangle", "straddle", "iron condor") and s.short_call is not None:
                s.suggestion = (f"⚠️ TESTED on the put side ({spot:g} ≤ {s.short_put:g}), still inside "
                                f"the tent — {tent}. Roll the untested CALL down to ≈{target_delta:.2f}Δ "
                                f"(its original delta) for more credit; that widens the breakeven.")
            else:
                s.suggestion = (f"⚠️ TESTED — {spot:g} ≤ {s.short_put:g} strike, {tent}. "
                                f"Roll down & out for a credit, or take assignment if you want the shares.")
            return s
        if s.short_call is not None and spot >= s.short_call:
            s.status = "tested"
            if s.kind in ("strangle", "straddle", "iron condor") and s.short_put is not None:
                s.suggestion = (f"⚠️ TESTED on the call side ({spot:g} ≥ {s.short_call:g}), still inside "
                                f"the tent — {tent}. Roll the untested PUT up to ≈{target_delta:.2f}Δ "
                                f"(its original delta) for more credit.")
            else:
                s.suggestion = (f"⚠️ TESTED — {spot:g} ≥ {s.short_call:g} strike, {tent}. "
                                f"Roll up & out for a credit.")
            return s

    # -- profit ladder --
    target, label = _ladder_target(s.days_held)
    if pct >= target:
        s.status = "close"
        s.suggestion = f"💰 CLOSE — {pct:.0f}% captured ({pct / 100 * cr * m * s.qty:,.0f} banked), hit the {label}"
        return s
    if pct >= roll_forward_pct:
        s.status = "roll_forward"
        s.suggestion = (f"📈 ROLL FORWARD — {pct:.0f}% captured: close it and re-sell the same "
                        f"strike{'s' if s.kind in ('strangle', 'straddle', 'iron condor') else ''} "
                        f"30–45 days out to bank the gain and add time")
        return s
    if s.dte is not None and s.dte <= window_dte:
        s.status = "window"
        s.suggestion = f"⏰ {s.dte} DTE — inside the {window_dte}-DTE window: roll or close even if healthy"
        return s
    if not spot and pct <= -15:
        s.status = "hold"
        s.suggestion = (f"🟡 {abs(pct):.0f}% against on the mark (no live spot to check the strikes) — "
                        f"{tent}. Check the chart.")
        return s
    s.status = "hold"
    where = ""
    if spot and s.short_put is not None and s.short_call is not None:
        where = f" · spot {spot:g} inside {s.short_put:g}–{s.short_call:g}"
    elif spot and s.short_put is not None:
        where = f" · spot {spot:g}, {(spot / s.short_put - 1) * 100:.1f}% above the strike"
    elif spot and s.short_call is not None:
        where = f" · spot {spot:g}, {(1 - spot / s.short_call) * 100:.1f}% below the strike"
    s.suggestion = f"hold — {pct:.0f}% captured{where} · {tent}"
    return s


def build(rows: list[dict], spot_of=None, **kw) -> list[Structure]:
    """Group + suggest in one go. spot_of(underlying) -> float | None."""
    out = []
    for s in group(rows):
        spot = None
        if spot_of is not None:
            try:
                spot = spot_of(s.underlying)
            except Exception:
                spot = None
        out.append(suggest(s, spot, **kw))
    out.sort(key=lambda s: (STATUS_ORDER.get(s.status, 9), s.underlying, s.expires))
    return out


def untested_side(s: Structure) -> str | None:
    """For a tested two-sided structure, which side to roll: 'call' or 'put'."""
    if s.status != "tested" or s.spot is None:
        return None
    if s.short_put is not None and s.short_call is not None:
        if s.spot <= s.short_put:
            return "call"
        if s.spot >= s.short_call:
            return "put"
    return None
