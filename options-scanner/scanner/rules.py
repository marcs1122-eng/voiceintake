"""Rulebook compliance — the scanner enforces the trader's own rules.

Checks a live position list (the rows `tastytrade_provider.get_positions`
returns) and account balances against hard limits, and returns a
traffic-light list the Trade Plan shows before it recommends anything.

Position counting follows the trader's convention: legs on the same
underlying and expiration are ONE position (a strangle is 1, a butterfly
is 1), stock and LEAPs (over 365 DTE) are excluded.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import bs
from .futures import product_for

# Defaults mirror the v3 rulebook; every one can be overridden per call.
LIMITS = {
    "max_positions": 20,
    "max_per_ticker": 3,
    "max_per_sector": 2,
    "max_bp_pct": 40.0,           # used derivative BP / net liq
    "max_futures_margin": 65_000.0,
    "beta_delta_min": -50.0,
    "beta_delta_max": 150.0,
}

SECTOR_TAGS = ("tech", "semis", "financials", "healthcare", "consumer",
               "industrials", "energy", "materials", "utilities", "reits", "china")

_OCC = re.compile(r"^([A-Z0-9]+)\s+(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")
_FUT = re.compile(r"^\.\/([A-Z0-9]+)\s+\S+\s+(\d{2})(\d{2})(\d{2})([CP])([\d.]+)$")


@dataclass
class RuleCheck:
    name: str
    value: float | None
    limit: float
    status: str          # "ok" | "warn" | "breach" | "n/a"
    detail: str = ""

    @property
    def icon(self) -> str:
        return {"ok": "🟢", "warn": "🟡", "breach": "🔴"}.get(self.status, "⚪")


def _status(value: float | None, limit: float, warn_at: float = 0.85,
            lower: float | None = None) -> str:
    if value is None:
        return "n/a"
    if lower is not None and value < lower:
        return "breach"
    if value > limit:
        return "breach"
    if value >= limit * warn_at:
        return "warn"
    return "ok"


# ---------------------------------------------------------------------------
# reading positions
# ---------------------------------------------------------------------------

def parse_option(symbol: str) -> dict | None:
    """Strike / put-call / root from a tastytrade option symbol."""
    s = (symbol or "").strip()
    m = _OCC.match(s)
    if m:
        root, _, _, _, cp, k = m.groups()
        return {"root": root, "strike": int(k) / 1000.0, "is_put": cp == "P", "futures": False}
    m = _FUT.match(s)
    if m:
        root, _, _, _, cp, k = m.groups()
        return {"root": "/" + re.sub(r"[FGHJKMNQUVXZ]\d$", "", root),
                "strike": float(k), "is_put": cp == "P", "futures": True}
    return None


def is_option_row(r: dict) -> bool:
    return "option" in str(r.get("type", "")).lower()


def position_groups(rows: list[dict], leap_days: int = 365) -> dict[tuple, list[dict]]:
    """{(underlying, expires): [legs]} for countable positions."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if not is_option_row(r):
            continue
        dte = r.get("dte")
        if dte is not None and dte > leap_days:
            continue
        groups[(r.get("underlying") or "", r.get("expires") or "")].append(r)
    return groups


def per_ticker(rows: list[dict]) -> Counter:
    return Counter(u for (u, _) in position_groups(rows))


def futures_root(symbol: str) -> str:
    """'/NGX6' -> '/NG', '/ESZ6' -> '/ES'; non-futures come back unchanged."""
    s = (symbol or "").strip()
    if not s.startswith("/"):
        return s
    return "/" + re.sub(r"[FGHJKMNQUVXZ]\d{1,2}$", "", s.lstrip("/"))


def sector_of(underlying: str, tags: dict[str, frozenset]) -> str:
    t = tags.get(underlying, frozenset())
    for s in SECTOR_TAGS:
        if s in t:
            return s
    prod = product_for(underlying) or product_for(futures_root(underlying))
    if prod:
        return "futures-" + prod.group
    if "etf" in t:
        return "etf"
    return "other"


def per_sector(rows: list[dict], tags: dict[str, frozenset]) -> Counter:
    seen = set()
    c: Counter = Counter()
    for (u, _) in position_groups(rows):
        c[sector_of(u, tags)] += 1
        seen.add(u)
    return c


def futures_margin(rows: list[dict]) -> float:
    """Rough initial margin tied up by short futures options, from the
    product registry (SPAN moves; the platform shows the live number)."""
    total = 0.0
    for r in rows:
        if not is_option_row(r) or r.get("direction") != "SHORT":
            continue
        u = r.get("underlying") or ""
        prod = product_for(u) or product_for("/" + re.sub(r"[FGHJKMNQUVXZ]\d$", "", u.lstrip("/")))
        if prod:
            total += prod.margin_estimate * float(r.get("qty") or 0)
    return total


# ---------------------------------------------------------------------------
# beta-weighted delta
# ---------------------------------------------------------------------------

def beta_weighted_delta(rows: list[dict], spot_of, beta_of, spy_spot: float,
                        r: float = 0.04) -> tuple[float | None, dict[str, float]]:
    """SPY-weighted portfolio delta: Σ delta × qty × multiplier × β × (S/S_spy).

    Option deltas come from Black-Scholes off each leg's mark (IV solved,
    then delta). Stock counts 1 per share. Returns (total, by_underlying);
    total is None when nothing could be priced.
    """
    if not spy_spot:
        return None, {}
    contrib: dict[str, float] = defaultdict(float)
    priced = False
    for row in rows:
        u = row.get("underlying") or ""
        qty = float(row.get("qty") or 0) * (-1.0 if row.get("direction") == "SHORT" else 1.0)
        try:
            spot = float(spot_of(u) or 0)
        except Exception:
            spot = 0.0
        if not spot or not qty:
            continue
        beta = beta_of(u)
        beta = 1.0 if beta is None else float(beta)
        if is_option_row(row):
            opt = parse_option(row.get("symbol", ""))
            dte = row.get("dte")
            mark = float(row.get("mark") or 0)
            if not opt or dte is None or mark <= 0:
                continue
            t = max(int(dte), 1) / 365.0
            prod = product_for(opt["root"]) if opt["futures"] else None
            mult = prod.multiplier if prod else 100.0
            # futures options quote in points; the IV solver wants price and
            # spot in the same units, which they already are
            iv = bs.implied_vol(mark, spot, opt["strike"], t, r, is_put=opt["is_put"])
            if iv <= 0:
                continue
            d = (bs.put_delta if opt["is_put"] else bs.call_delta)(spot, opt["strike"], iv, t, r)
            delta_shares = d * qty * mult
        else:
            delta_shares = qty                     # stock / ETF: 1 per share
        contrib[u] += delta_shares * beta * (spot / spy_spot)
        priced = True
    if not priced:
        return None, {}
    return round(sum(contrib.values()), 1), {k: round(v, 1) for k, v in contrib.items()}


# ---------------------------------------------------------------------------
# the panel
# ---------------------------------------------------------------------------

def check(rows: list[dict], tags: dict[str, frozenset], balances: dict | None = None,
          beta_delta: float | None = None, limits: dict | None = None) -> list[RuleCheck]:
    L = {**LIMITS, **(limits or {})}
    out = []

    groups = position_groups(rows)
    n = len(groups)
    out.append(RuleCheck("Open positions", n, L["max_positions"],
                         _status(n, L["max_positions"]),
                         f"{n} of {L['max_positions']} (strangle = 1, fly = 1; stock & LEAPs excluded)"))

    pt = per_ticker(rows)
    worst = max(pt.values()) if pt else 0
    over = [f"{u} ({c})" for u, c in pt.items() if c > L["max_per_ticker"]]
    out.append(RuleCheck("Per ticker", worst, L["max_per_ticker"],
                         _status(worst, L["max_per_ticker"], warn_at=1.0),
                         ("over: " + ", ".join(over)) if over else
                         (f"max {worst} on {', '.join(u for u, c in pt.items() if c == worst)}" if pt else "none")))

    ps = per_sector(rows, tags)
    worst_s = max(ps.values()) if ps else 0
    over_s = [f"{s} ({c})" for s, c in ps.items() if c > L["max_per_sector"]]
    out.append(RuleCheck("Per sector", worst_s, L["max_per_sector"],
                         _status(worst_s, L["max_per_sector"], warn_at=1.0),
                         ("over: " + ", ".join(over_s)) if over_s else
                         ", ".join(f"{s} {c}" for s, c in ps.most_common(4))))

    bp = None
    if balances and balances.get("net_liq"):
        used = balances.get("bp_used")
        if used is not None:
            bp = used / balances["net_liq"] * 100.0
    out.append(RuleCheck("Buying power used", round(bp, 1) if bp is not None else None,
                         L["max_bp_pct"], _status(bp, L["max_bp_pct"]),
                         f"{bp:.0f}% of net liq" if bp is not None else "connect tastytrade for balances"))

    fm = futures_margin(rows)
    if balances and balances.get("futures_margin") is not None:
        fm = float(balances["futures_margin"])
    out.append(RuleCheck("Futures sleeve", round(fm), L["max_futures_margin"],
                         _status(fm, L["max_futures_margin"]),
                         f"${fm:,.0f} of ${L['max_futures_margin']:,.0f}"))

    if beta_delta is None:
        st = "n/a"
    elif beta_delta < L["beta_delta_min"] or beta_delta > L["beta_delta_max"]:
        st = "breach"
    elif beta_delta > L["beta_delta_max"] * 0.85 or beta_delta < L["beta_delta_min"] * 0.85:
        st = "warn"
    else:
        st = "ok"
    out.append(RuleCheck("β-delta (SPY)", beta_delta, L["beta_delta_max"], st,
                         (f"{beta_delta:+.0f} · band {L['beta_delta_min']:+.0f} to {L['beta_delta_max']:+.0f}; "
                          "a QQQ call credit spread is the lever") if beta_delta is not None
                         else "needs live quotes"))
    return out


def worst_status(checks: list[RuleCheck]) -> str:
    order = {"breach": 3, "warn": 2, "ok": 1, "n/a": 0}
    return max(checks, key=lambda c: order[c.status]).status if checks else "n/a"
