"""Presentation helpers — the plain-English layer.

Everything a first-time user sees goes through here: the one-line verdict
on a trade, the signal chips, the scan presets, and the printable brief
built from a scan result. Kept out of app.py so it is testable and so the
CLI and the routines can produce the same words.
"""

from __future__ import annotations

import datetime as dt

from .strategies import CashSecuredPut

# ---------------------------------------------------------------------------
# presets — one click instead of eight sliders
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "Custom": {},
    "Wheel · conservative": dict(
        timeframe="1d", tags=["blue-chip", "etf"], dte=(21, 45),
        delta=(0.10, 0.25), min_annual=10.0, min_oi=200,
        blurb="Quality names only, 21-45 days, 10-25 delta. Assignment is welcome."),
    "Income · balanced": dict(
        timeframe="1d", tags=[], dte=(7, 45), delta=(0.15, 0.35),
        min_annual=15.0, min_oi=100,
        blurb="The whole universe, 15-35 delta, 15%+ annualized."),
    "Scalp · intraday": dict(
        timeframe="5m", tags=["etf", "high-iv"], dte=(0, 7), delta=(0.20, 0.45),
        min_annual=0.0, min_oi=100,
        blurb="5-minute signals, this week's expiries, liquid ETFs and high-IV names."),
    "Futures · Wednesday": dict(
        timeframe="1d", tags=["fut-liquid"], dte=(30, 60), delta=(0.15, 0.30),
        min_annual=12.0, min_oi=50,
        blurb="The liquid futures options books, 30-60 days, margin-secured."),
    "Leveraged · 2-3x": dict(
        timeframe="1d", tags=["leveraged"], dte=(7, 30), delta=(0.15, 0.30),
        min_annual=30.0, min_oi=500,
        blurb="TQQQ, SOXL, SPXL, TNA, LABU, NUGT, UCO, BOIL, TMF and the 2x single-stock "
              "funds. Fat premium, real decay — 1-4 week trades, never the wheel."),
    "Top picks · today": dict(
        timeframe="1d", tags=[], dte=(21, 45), delta=(0.15, 0.30),
        min_annual=15.0, min_oi=200, top_n=10,
        blurb="Everything, 21-45 days, 15-30 delta — the ten best-scored names only."),
    "Gap down · today": dict(
        timeframe="1d", tags=[], dte=(21, 45), delta=(0.15, 0.30),
        min_annual=12.0, min_oi=100, gap=-2.0,
        blurb="Only names that opened 2%+ below yesterday's close. Premium is richest "
              "right after the gap; confirm the gap is not earnings or a downgrade."),
    "Diversify · my book": dict(
        timeframe="1d", tags=[], dte=(21, 45), delta=(0.15, 0.30),
        min_annual=10.0, min_oi=100, diversify=True,
        blurb="Scans the sectors that move least with what you already hold — the "
              "Correlation tab's diversifiers plus the stocks inside them."),
}

# The Correlation tab's diversifiers → the names to actually scan for entries.
# Each entry: yahoo symbol of the diversifier → (label, tickers in that bucket).
DIVERSIFY_BUCKETS: dict[str, tuple[str, list[str]]] = {
    "GLD": ("gold", ["GLD", "/GC", "NEM", "GDX"]),
    "TLT": ("long bonds", ["TLT", "/ZN", "/ZB"]),
    "ZN=F": ("rates", ["/ZN", "TLT", "IEF"]),
    "XLU": ("utilities", ["XLU", "SO", "DUK", "NEE", "D", "AEP"]),
    "XLP": ("staples", ["XLP", "KO", "PEP", "PG", "WMT", "COST", "PM", "MO"]),
    "XLV": ("healthcare", ["XLV", "JNJ", "MRK", "PFE", "LLY", "UNH", "ABBV", "AMGN"]),
    "XLE": ("energy", ["XLE", "XOM", "CVX", "COP", "OXY", "SLB", "/CL"]),
    "FXI": ("china", ["FXI", "BABA", "PDD", "JD", "BIDU"]),
    "IWM": ("small caps", ["IWM", "/RTY"]),
    "USO": ("oil", ["USO", "/CL", "XLE", "XOM"]),
}


def diversify_universe(ideas: list[tuple[str, float]], known: set[str],
                       max_buckets: int = 4, max_names: int = 30) -> list[str]:
    """ideas = [(yahoo symbol, avg corr to the book)] lowest first. Returns the
    tickers to scan, restricted to names the scanner knows (plus futures roots)."""
    out: list[str] = []
    for ysym, _ in ideas[:max_buckets]:
        _, names = DIVERSIFY_BUCKETS.get(ysym, (ysym, [ysym]))
        for t in names:
            if (t in known or t.startswith("/")) and t not in out:
                out.append(t)
    return out[:max_names]

DEFAULTS = dict(timeframe="1d", tags=[], dte=(7, 45), delta=(0.10, 0.35),
                min_annual=12.0, min_oi=100, blurb="")


def preset(name: str) -> dict:
    return {**DEFAULTS, **PRESETS.get(name, {})}


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------

def verdict(c: CashSecuredPut) -> str:
    """One sentence a beginner can act on."""
    basis = "margin" if c.is_futures else "cash"
    return (f"Sell the {c.ticker} {c.strike:g} put, {c.expiry:%b %d} — collect "
            f"${c.premium:,.0f}, keep it about {c.prob_otm_pct:.0f}% of the time, "
            f"ties up ${c.capital:,.0f} {basis}.")


def chips(c: CashSecuredPut) -> list[str]:
    """Traffic-light chips for the card. Green = the signal is on."""
    out = []
    out.append(("🟢" if c.rsi_14 <= 30 else "⚪") + f" RSI {c.rsi_14:.0f}")
    out.append(("🟢" if "LowerBB" in c.entry_signals else "⚪") + " band")
    out.append(("🟢" if "50SMA" in c.entry_signals else "⚪") + " 50-SMA")
    if c.iv_rank is not None:
        light = "🟢" if c.iv_rank >= 30 else ("🟡" if c.iv_rank >= 20 else "🔴")
        out.append(f"{light} IVR {c.iv_rank:.0f}")
    if c.em_cushion is not None:
        out.append(("🟢" if c.em_cushion >= 1.0 else "🟡" if c.em_cushion >= 0.7 else "⚪")
                   + f" {c.em_cushion:.1f}× EM")
    if c.earnings_before_expiry:
        out.append("🔴 earnings before expiry")
    return out


def why(c: CashSecuredPut, at_day_low: bool = False) -> str:
    bits = sorted(c.entry_signals)
    if at_day_low:
        bits.append("at the low of day")
    if c.iv_rank is not None and c.iv_rank >= 30:
        bits.append(f"IVR {c.iv_rank:.0f}")
    return ", ".join(bits) if bits else "yield + liquidity"


# ---------------------------------------------------------------------------
# printable brief from a scan
# ---------------------------------------------------------------------------

FUTURES_POSTURE = ["/ES", "/NQ", "/ZN", "/CL", "/GC", "/NG"]


def brief_from_result(result, tags: dict, picks: list[tuple[float, CashSecuredPut]],
                      checks: list = (), earnings: list[dict] = (),
                      when: dt.datetime | None = None, held: list[str] = ()) -> dict:
    """The brief_pdf JSON for today's scan — same schema the routines use."""
    when = when or dt.datetime.now()
    rows = []
    for tk in FUTURES_POSTURE:
        info = result.infos.get(tk)
        if info is None:
            continue
        rows.append({"sym": tk, "last": f"{info.spot:,.2f}",
                     "chg": f"{info.day_change_pct:+.2f}%", "rsi": f"{info.rsi_14:.1f}",
                     "read": "oversold" if info.rsi_14 <= 30 else ("overbought" if info.rsi_14 >= 70 else "neutral")})
    cands = []
    for s, c in picks:
        cands.append({
            "ticker": c.ticker, "spot": f"{c.spot:,.2f}", "rsi": f"{c.rsi_14:.1f}",
            "signals": " · ".join(chips(c)),
            "zone": f"Sell {c.strike:g}P {c.expiry:%m/%d}",
            "note": f"${c.premium:,.0f} credit · {c.prob_otm_pct:.0f}% P(OTM) · score {s:g}",
            "size": "spread only" if (not c.is_futures and c.strike > 450) else "",
        })
    loud_names = [tk for tk, i in result.infos.items()
                  if i.rsi_14 <= 30 and ({"blue-chip", "etf"} & tags.get(tk, frozenset()))]
    loud = ("Quality at RSI 30 or under: " + " · ".join(
        f"{tk} {result.infos[tk].rsi_14:.0f}" for tk in sorted(loud_names, key=lambda t: result.infos[t].rsi_14)[:10])
        if loud_names else "")
    todo = []
    for c in checks:
        if getattr(c, "status", "") in ("breach", "warn"):
            todo.append(f"{c.icon} {c.name}: {c.detail}")
    for e in earnings[:6]:
        todo.append(f"Earnings {e['Earnings']} · {e['Ticker']}" + (" (held)" if e.get("In book") else ""))
    return {
        "title": "Options Trade Plan",
        "date": when.strftime("%A %m/%d/%Y"),
        "pulled": when.strftime("%I:%M%p").lstrip("0").lower() + " ET",
        "source": f"{len(result.infos)} names scanned · {len(result.csps)} puts passed",
        "lede": "Today's scan, boiled down to the trades worth putting on.",
        "posture": {"rows": rows} if rows else {},
        "candidates": cands,
        "loud": loud,
        "todo": todo,
        "footer": "STRIKE ZONES ARE STARTING POINTS, NOT ORDERS. Confirm live bid/ask "
                  "before entering. Exit plan: 25% of max day one, 30% day two, then "
                  "50% or 21 DTE.",
    }
