"""BOUNCE — beaten-down, liquid, quality names set up for a 1-3 day bounce.

The trade: sell a 0.20-0.25 delta put, 30-45 days out, on a quality name
that has been sold hard into its lower Bollinger Band, and close it in one
to three days when the bounce pays.

Trigger (all three):
  1. RSI(14) daily <= 32
  2. close at or below the lower Bollinger Band (20, 2), or within 1% above it
  3. down >= 2% today, OR down >= 8% over the last 5 sessions

Quality:
  * price above the 200-day SMA, or no more than 10% below it (a name in
    free fall is a knife, not a bounce)
  * no earnings inside the next 5 trading days

Rank: RSI lowest first, then furthest below the band, then the 5-day drop.
Flags: KNIFE (down 25%+ in a month), SEMIS (scalp lane only), earnings.

Near-misses (RSI passes, band within 6%, some selling) are kept in a second
tier so a green-tape day still shows what is close.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from . import bs
from .data import DataProvider, UnderlyingInfo

BOUNCE_ETFS = ["SPY", "QQQ", "IWM", "GLD", "TLT", "XLE", "XLV", "XLI", "XLF", "XLK",
               "XLY", "XLC", "XLU", "XBI", "KRE", "XOP", "GDX", "SOXL"]
BOUNCE_FUTURES = ["/GC", "/MGC", "/CL", "/NG", "/6E", "/ZN", "/ZB", "/ZS"]
BOUNCE_LEVERAGED = ["TQQQ", "SOXL", "SPXL", "UPRO", "TNA", "LABU", "NUGT", "JNUG", "UCO",
                    "BOIL", "TMF", "FAS", "YINN", "ERX", "TSLL", "NVDL", "MSTU", "CONL",
                    "AMDL", "AMZU", "GGLL", "MSFU", "METU", "BITX"]
BANNED = {"CRDO", "SLV", "AAL", "NFLX"}
SEMIS = {"MU", "WDC", "SNDK", "AMD", "AVGO", "NVDA", "INTC", "ARM", "SMCI"}

# TradingView alert mirror — paste into an alert on a 1D chart, "once per bar close".
TV_ALERT = """// BOUNCE — TradingView alert mirror (1D, once per bar close)
// Condition A: RSI(14) crossing DOWN 32
// Condition B: Close crossing DOWN Bollinger Lower Band (20, 2)
// Set both in the same alert with "AND" (Pine v5 equivalent below).
//@version=5
indicator("BOUNCE alert", overlay=true)
rsiV  = ta.rsi(close, 14)
basis = ta.sma(close, 20)
lower = basis - 2.0 * ta.stdev(close, 20)
rsiCross  = ta.crossunder(rsiV, 32)
bandCross = ta.crossunder(close, lower)
bounce = rsiCross and bandCross
plotshape(bounce, style=shape.triangleup, location=location.belowbar, color=color.lime, size=size.small)
alertcondition(bounce, title="BOUNCE setup", message="{{ticker}} BOUNCE: RSI<32 and close under lower BB")
// Looser variant (either condition, then confirm by hand):
// alertcondition(rsiCross or bandCross, title="BOUNCE watch", message="{{ticker}} RSI or band cross")
"""


@dataclass
class BounceConfig:
    rsi_max: float = 32.0
    band_tol_pct: float = 1.0        # within this % ABOVE the lower band still counts
    day_drop_pct: float = -2.0       # today's move at or below this ...
    week_drop_pct: float = -8.0      # ... or the 5-session move at or below this
    sma200_tol_pct: float = -10.0    # no more than this far below the 200-day
    earnings_days: int = 5           # trading days; ~7 calendar days
    knife_month_pct: float = -25.0
    delta_lo: float = 0.20
    delta_hi: float = 0.25
    min_dte: int = 30
    max_dte: int = 45
    min_price: float = 15.0
    min_avg_volume: float = 2_000_000.0
    near_band_pct: float = 6.0       # near-miss tier: band within this %
    max_workers: int = 8


@dataclass
class BounceHit:
    ticker: str
    price: float
    day_pct: float
    rsi: float
    vs_bb_pct: float                  # % above (+) / below (-) the lower band
    pct_5d: float | None
    pct_1m: float | None
    vs_sma200_pct: float | None
    avg_vol: float | None
    earnings: dt.date | None
    earnings_source: str = ""
    kind: str = "stock"               # stock | etf | futures
    status: str = "hit"               # hit | near
    strike: float | None = None
    delta: float | None = None
    credit: float | None = None       # per contract, dollars
    expiry: dt.date | None = None
    dte: int | None = None
    flags: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def rank_key(self) -> tuple:
        return (0 if self.status == "hit" else 1, self.rsi, self.vs_bb_pct, self.pct_5d or 0.0)

    @property
    def earnings_txt(self) -> str:
        if self.earnings is None:
            return "—"
        return self.earnings.strftime("%m/%d") + ("" if self.earnings_source == "broker" else "?")


# ---------------------------------------------------------------------------

def stats_from_bars(bars: list[tuple[float, float]]) -> dict:
    """5-day / 1-month moves, 200-day average and 10-day average volume."""
    closes = [c for c, _ in bars]
    vols = [v for _, v in bars]
    out: dict = {"pct_5d": None, "pct_1m": None, "sma200": None, "avg_vol10": None}
    if len(closes) >= 6 and closes[-6]:
        out["pct_5d"] = (closes[-1] / closes[-6] - 1.0) * 100.0
    if len(closes) >= 22 and closes[-22]:
        out["pct_1m"] = (closes[-1] / closes[-22] - 1.0) * 100.0
    if len(closes) >= 200:
        out["sma200"] = sum(closes[-200:]) / 200.0
    if len(vols) >= 10:
        out["avg_vol10"] = sum(vols[-10:]) / 10.0
    return out


def evaluate(info: UnderlyingInfo, bars: list[tuple[float, float]] | None = None,
             cfg: BounceConfig | None = None, today: dt.date | None = None,
             kind: str = "stock", stats: dict | None = None) -> BounceHit | None:
    """Score one name. Returns a hit, a near-miss, or None."""
    cfg = cfg or BounceConfig()
    today = today or dt.date.today()
    tk = info.ticker.upper()
    if tk in BANNED or not info.spot:
        return None
    if kind == "stock" and info.spot < cfg.min_price:
        return None
    st = stats or stats_from_bars(bars or [])
    spot = info.spot
    vs_bb = (spot / info.boll_lower - 1.0) * 100.0 if info.boll_lower else 99.0
    vs_sma = (spot / st["sma200"] - 1.0) * 100.0 if st.get("sma200") else None
    hit = BounceHit(ticker=tk, price=spot, day_pct=info.day_change_pct, rsi=info.rsi_14,
                    vs_bb_pct=vs_bb, pct_5d=st.get("pct_5d"), pct_1m=st.get("pct_1m"),
                    vs_sma200_pct=vs_sma, avg_vol=st.get("avg_vol10"), earnings=info.next_earnings,
                    earnings_source="broker" if info.iv_source == "tastytrade" else "yahoo",
                    kind=kind)

    # -- triggers --
    if info.rsi_14 > cfg.rsi_max:
        return None                                   # never interesting
    if vs_bb > cfg.band_tol_pct:
        hit.misses.append(f"{vs_bb:.1f}% above band")
    moved = (info.day_change_pct <= cfg.day_drop_pct) or \
            (st.get("pct_5d") is not None and st["pct_5d"] <= cfg.week_drop_pct)
    if not moved:
        hit.misses.append("no 2%-day / 8%-week drop")

    # -- quality --
    if vs_sma is not None and vs_sma < cfg.sma200_tol_pct:
        hit.misses.append(f"{vs_sma:.0f}% under 200d")
        hit.flags.append(f"below 200d {vs_sma:.0f}%")
    if info.next_earnings is not None:
        days = (info.next_earnings - today).days
        if 0 <= days <= int(cfg.earnings_days * 7 / 5):
            hit.misses.append(f"earnings {info.next_earnings:%m/%d}")
            hit.flags.append(f"earnings {info.next_earnings:%m/%d}")
    if kind == "stock" and st.get("avg_vol10") is not None and st["avg_vol10"] < cfg.min_avg_volume:
        hit.misses.append(f"avg vol {st['avg_vol10'] / 1e6:.1f}M")

    # -- flags that do not fail it --
    if st.get("pct_1m") is not None and st["pct_1m"] <= cfg.knife_month_pct:
        hit.flags.append(f"KNIFE {st['pct_1m']:.0f}% 1m")
    if tk in SEMIS:
        hit.flags.append("SEMIS · scalp only")
    if kind != "stock":
        hit.flags.append(kind.upper())
    if tk in BOUNCE_LEVERAGED:
        hit.flags.append("LEVERAGED · day trade only")

    if not hit.misses:
        hit.status = "hit"
        return hit
    # near-miss tier: RSI passed and the band is close — shown with the reason it missed
    if vs_bb <= cfg.near_band_pct:
        hit.status = "near"
        return hit
    return None


def pick_strike(provider: DataProvider, info: UnderlyingInfo, cfg: BounceConfig | None = None) -> dict:
    """0.20-0.25 delta put, 30-45 DTE, nearest expiry first. {} if none."""
    cfg = cfg or BounceConfig()
    today = dt.date.today()
    exps = [e for e in info.expiries if cfg.min_dte <= (e - today).days <= cfg.max_dte]
    for e in sorted(exps):
        try:
            chain = provider.chain(info.ticker, e)
        except Exception:
            continue
        t = max(chain.dte, 1) / 365.0
        best = None
        for q in chain.puts:
            if q.mid <= 0 or q.iv <= 0 or q.strike >= chain.spot:
                continue
            try:
                d = abs(bs.put_delta(chain.spot, q.strike, q.iv, t, q=info.dividend_yield))
            except ValueError:
                continue
            if cfg.delta_lo <= d <= cfg.delta_hi:
                score = abs(d - (cfg.delta_lo + cfg.delta_hi) / 2)
                if best is None or score < best[0]:
                    best = (score, q, d)
        if best:
            _, q, d = best
            return {"strike": q.strike, "delta": round(d, 2), "credit": round(q.mid * chain.multiplier),
                    "expiry": e, "dte": chain.dte}
    return {}


def run_bounce(provider: DataProvider, tickers: list[str], cfg: BounceConfig | None = None,
               price_strikes: bool = True, progress=None, today: dt.date | None = None,
               kinds: dict[str, str] | None = None) -> tuple[list[BounceHit], dict[str, str]]:
    """Scan every ticker; returns (hits + near-misses ranked, errors)."""
    cfg = cfg or BounceConfig()
    kinds = kinds or {}
    try:
        provider.prefetch(tickers)
    except Exception:
        pass
    out: list[BounceHit] = []
    errors: dict[str, str] = {}

    def one(tk: str):
        info = provider.underlying(tk)
        bars = provider.daily_bars(tk, 260)
        kind = kinds.get(tk) or ("futures" if tk.startswith("/") else
                                 ("etf" if tk in BOUNCE_ETFS or tk in BOUNCE_LEVERAGED else "stock"))
        return evaluate(info, bars, cfg, today, kind=kind), info

    with ThreadPoolExecutor(max_workers=cfg.max_workers) as ex:
        futs = {ex.submit(one, tk): tk for tk in tickers}
        for i, f in enumerate(as_completed(futs)):
            tk = futs[f]
            try:
                hit, info = f.result()
            except Exception as exc:
                errors[tk] = str(exc)[:120]
                hit, info = None, None
            if hit is not None:
                if price_strikes and hit.status == "hit":
                    try:
                        hit.__dict__.update(pick_strike(provider, info, cfg))
                    except Exception:
                        pass
                out.append(hit)
            if progress:
                progress(i, len(tickers), tk)
    out.sort(key=lambda h: h.rank_key)
    return out, errors


def to_rows(hits: list[BounceHit]) -> list[dict]:
    rows = []
    for h in hits:
        rows.append({
            "Ticker": h.ticker, "Price": round(h.price, 2), "Day %": round(h.day_pct, 2),
            "RSI": round(h.rsi, 1), "% vs lower BB": round(h.vs_bb_pct, 2),
            "5-day %": round(h.pct_5d, 1) if h.pct_5d is not None else None,
            "1-mo %": round(h.pct_1m, 1) if h.pct_1m is not None else None,
            "vs 200d %": round(h.vs_sma200_pct, 1) if h.vs_sma200_pct is not None else None,
            "Earnings": h.earnings_txt,
            "Put strike": h.strike, "Δ": h.delta, "Expiry": h.expiry.strftime("%m/%d/%Y") if h.expiry else None,
            "DTE": h.dte, "Est. credit $": h.credit,
            "Flags": " · ".join(h.flags),
            "Status": "HIT" if h.status == "hit" else "near: " + "; ".join(h.misses),
        })
    return rows


def summary(hits: list[BounceHit]) -> str:
    real = [h for h in hits if h.status == "hit"]
    near = [h for h in hits if h.status == "near"]
    top = ", ".join(f"{h.ticker} (RSI {h.rsi:.0f})" for h in real[:5])
    s = f"{len(real)} hit(s), {len(near)} near-miss(es)."
    if real:
        s += f" Top by bounce odds: {top}."
    return s
