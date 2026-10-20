"""Yesterday's biggest losers and winners — the rotation list.

Sector rotation means yesterday's worst group is often today's best. This
ranks the previous completed session's moves across the liquid universe
(price > $15, 10-day average volume above the floor) and shows today's
follow-through next to each, so the morning brief can say "software was
the worst group yesterday; here is what is bouncing".

"Yesterday" is the last completed session: before the open that is the
last bar; during the session it is the bar before today's partial one.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .data import DataProvider


@dataclass
class Mover:
    ticker: str
    close: float            # yesterday's close
    yday_pct: float         # yesterday's close-to-close move
    today_pct: float | None # today so far (None before the open)
    rsi: float | None
    avg_vol: float | None
    sector: str = ""

    @property
    def follow_through(self) -> str:
        if self.today_pct is None:
            return ""
        if self.yday_pct < 0:
            return "bouncing" if self.today_pct >= 1.0 else ("still falling" if self.today_pct <= -1.0 else "flat")
        return "fading" if self.today_pct <= -1.0 else ("still running" if self.today_pct >= 1.0 else "flat")


def _session_change(bars: list[tuple[float, float]], last_is_today: bool) -> tuple[float, float, float | None] | None:
    closes = [c for c, _ in bars]
    if last_is_today:
        if len(closes) < 3:
            return None
        y_close, y_prev, today = closes[-2], closes[-3], closes[-1]
        return y_close, (y_close / y_prev - 1) * 100, (today / y_close - 1) * 100
    if len(closes) < 2:
        return None
    return closes[-1], (closes[-1] / closes[-2] - 1) * 100, None


def top_movers(provider: DataProvider, tickers: list[str], n: int = 5, min_price: float = 15.0,
               min_avg_volume: float = 1_000_000.0, tags: dict | None = None,
               today: dt.date | None = None, workers: int = 8) -> tuple[list[Mover], list[Mover]]:
    """(losers, winners) from the last completed session, n each."""
    from .rules import sector_of
    today = today or dt.date.today()
    tags = tags or {}
    rows: list[Mover] = []

    def one(tk: str) -> Mover | None:
        bars = provider.daily_bars(tk, 30)
        if len(bars) < 3:
            return None
        last_date = provider.last_bar_date(tk)
        ch = _session_change(bars, last_is_today=(last_date == today))
        if ch is None:
            return None
        close, y_pct, t_pct = ch
        if close < min_price:
            return None
        vols = [v for _, v in bars[-10:]]
        avg_vol = sum(vols) / len(vols) if vols else None
        if avg_vol is not None and avg_vol and avg_vol < min_avg_volume:
            return None
        rsi = None
        try:
            rsi = provider.underlying(tk).rsi_14
        except Exception:
            pass
        return Mover(tk, close, y_pct, t_pct, rsi, avg_vol, sector_of(tk, tags))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(one, t) for t in tickers]):
            try:
                m = f.result()
            except Exception:
                m = None
            if m is not None:
                rows.append(m)
    losers = sorted([m for m in rows if m.yday_pct < 0], key=lambda m: m.yday_pct)[:n]
    winners = sorted([m for m in rows if m.yday_pct > 0], key=lambda m: -m.yday_pct)[:n]
    return losers, winners


def to_rows(movers: list[Mover]) -> list[dict]:
    return [{
        "Ticker": m.ticker, "Sector": m.sector, "Yesterday close": round(m.close, 2),
        "Yesterday %": round(m.yday_pct, 2),
        "Today %": round(m.today_pct, 2) if m.today_pct is not None else None,
        "Now": m.follow_through, "RSI": round(m.rsi, 1) if m.rsi is not None else None,
        "Avg vol (M)": round(m.avg_vol / 1e6, 1) if m.avg_vol else None,
    } for m in movers]


def sector_story(losers: list[Mover], winners: list[Mover]) -> str:
    """One line: which group sold off yesterday and whether it is bouncing."""
    from collections import Counter
    bits = []
    for label, group in (("losers", losers), ("winners", winners)):
        if not group:
            continue
        sec = Counter(m.sector for m in group if m.sector and m.sector != "other").most_common(1)
        lead = f"{sec[0][0]} ({sec[0][1]} of {len(group)})" if sec else "mixed sectors"
        ft = Counter(m.follow_through for m in group if m.follow_through).most_common(1)
        bits.append(f"yesterday's {label}: {lead}" + (f", today mostly {ft[0][0]}" if ft else ""))
    return "; ".join(bits).capitalize() + "." if bits else ""
