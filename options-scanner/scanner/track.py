"""Track record — the scanner grades its own picks.

Every morning the top put-sale candidates get logged. At 7, 14 and 30 days
(and at expiry) each pick is graded against what actually happened: is the
put still out of the money, did price ever trade through the strike, how
much of the credit the 50%-rule exit would have captured. The Scorecard tab
then shows win rates by signal, sector and strategy.

Picks live in a JSONL file (one JSON object per line, append-only) so the
history survives redeploys when the file is committed to the repo — which
is exactly what the morning routine does.

    python3 -m scanner.track record  --from-brief brief.json
    python3 -m scanner.track grade   [--source demo|yahoo|tasty]
    python3 -m scanner.track show
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field

from . import bs
from .data import DataProvider
from .futures import product_for

DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "track_record.jsonl"
HORIZONS = (7, 14, 30)


@dataclass
class Pick:
    picked_on: str            # ISO date
    ticker: str
    strategy: str             # "short put" | "short call"
    strike: float
    expiry: str               # ISO date
    dte: int
    spot: float
    mid: float                # per-share credit at pick time
    multiplier: float = 100.0
    delta: float = 0.0
    prob_otm_pct: float = 0.0
    iv: float = 0.0           # the strike's IV at pick time (for re-pricing)
    iv_rank: float | None = None
    em_cushion: float | None = None
    rsi: float | None = None
    signals: list[str] = field(default_factory=list)
    sector: str = ""
    score: float = 0.0
    source: str = "scan"      # "scan" | "brief"
    grades: dict = field(default_factory=dict)   # {"7": {...}, "expiry": {...}}

    @property
    def key(self) -> tuple:
        # strategy is part of the key: a put and a call can share a ticker,
        # strike and expiry on the same day and are not the same pick
        return (self.picked_on, self.ticker, self.strategy, self.strike, self.expiry)

    @property
    def premium(self) -> float:
        return self.mid * self.multiplier


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def load(path: pathlib.Path = DEFAULT_PATH) -> list[Pick]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(Pick(**json.loads(line)))
    return out


def save(picks: list[Pick], path: pathlib.Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(asdict(p)) + "\n" for p in picks))


def record(new: list[Pick], path: pathlib.Path = DEFAULT_PATH) -> int:
    """Append picks not already on file. Returns how many were added."""
    have = {p.key for p in load(path)}
    fresh = [p for p in new if p.key not in have]
    if fresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            for p in fresh:
                f.write(json.dumps(asdict(p)) + "\n")
    return len(fresh)


# ---------------------------------------------------------------------------
# building picks
# ---------------------------------------------------------------------------

SECTOR_TAGS = ("tech", "semis", "financials", "healthcare", "consumer",
               "industrials", "energy", "materials", "utilities", "reits", "china")


def sector_of(tags: frozenset, ticker: str = "") -> str:
    for t in SECTOR_TAGS:
        if t in tags:
            return t
    prod = product_for(ticker)
    if prod:
        return "futures-" + prod.group
    if "etf" in tags:
        return "etf"
    return "other"


def picks_from_scan(result, tags: dict, top_n: int = 5, min_score: float = 70.0,
                    min_prob: float = 65.0, today: dt.date | None = None) -> list[Pick]:
    """Mirror the Trade Plan's selection: best-scored strike per ticker that
    clears the quality bar, top_n of them."""
    from .scan import ScanConfig, score_csp
    today = today or dt.date.today()
    cfg = ScanConfig()
    seen, out = set(), []
    for c in result.csps:
        s = score_csp(c, tags.get(c.ticker, frozenset()), cfg)
        if c.ticker in seen or s < min_score or c.prob_otm_pct < min_prob:
            continue
        seen.add(c.ticker)
        out.append(Pick(
            picked_on=today.isoformat(), ticker=c.ticker, strategy="short put",
            strike=c.strike, expiry=c.expiry.isoformat(), dte=c.dte, spot=c.spot,
            mid=c.mid, multiplier=c.multiplier, delta=c.delta,
            prob_otm_pct=c.prob_otm_pct, iv=c.iv, iv_rank=c.iv_rank,
            em_cushion=c.em_cushion, rsi=c.rsi_14,
            signals=sorted(c.entry_signals),
            sector=sector_of(tags.get(c.ticker, frozenset()), c.ticker),
            score=s, source="scan"))
        if len(out) == top_n:
            break
    return out


def picks_from_brief(brief: dict, today: dt.date | None = None) -> list[Pick]:
    """A morning-brief JSON (the brief_pdf schema) has ticker/spot/rsi and a
    strike zone like "Sell 125P", "172-177P", "Oct 16 310P · 0.24 delta · ~4.40"
    or, on the fade side, "Oct 16 230C / 240C spread". We log the strike that
    carries the P or C suffix (midpoint of a range, the short strike of a
    spread), the named expiry when the zone has one (else a nominal 45 days),
    plus the delta and mid when they are there, so the pick can be graded on
    direction and drawdown."""
    import re
    today = today or dt.date.today()
    out = []
    for c in brief.get("candidates", []):
        zone = str(c.get("zone", ""))
        strike, kind = _zone_strike_kind(zone)
        if strike is None or not c.get("spot"):
            continue
        expiry = _zone_expiry(zone, today) or today + dt.timedelta(days=45)
        m = re.search(r"(0\.\d+)\s*delta", zone)
        delta = float(m.group(1)) if m else 0.0
        m = re.search(r"~\s*(\d+(?:\.\d+)?)", zone)
        mid = float(m.group(1)) if m else 0.0
        spot = float(str(c["spot"]).replace(",", ""))
        rsi = float(c["rsi"]) if c.get("rsi") not in (None, "") else None
        out.append(Pick(
            picked_on=today.isoformat(), ticker=str(c["ticker"]).upper(),
            strategy=f"short {kind}", strike=strike,
            expiry=expiry.isoformat(), dte=(expiry - today).days,
            spot=spot, mid=mid, delta=delta, rsi=rsi,
            signals=[s.strip() for s in str(c.get("signals", "")).split("·") if s.strip()],
            source="brief"))
    return out


def _zone_strike_kind(zone: str) -> tuple[float | None, str]:
    """Strike and option kind from a brief's zone string.

    "310P" -> (310, "put"); "172-177P" -> (174.5, "put") — a range is a zone,
    so we take its midpoint. "515P / 495P spread" -> (515, "put") and
    "230C / 240C spread" -> (230, "call") — each leg carries its own suffix,
    so the FIRST one matches and that is the short strike, which is the leg
    that actually gets tested. Only numbers carrying a P or C count, so
    "Oct 16 310P" is 310 and not the average of 16 and 310.

    Falls back to (first number, "put") for a bare zone like "125 area",
    since every untagged zone we have ever written has been a put.
    """
    import re
    for suffix, kind in (("P", "put"), ("C", "call")):
        m = re.search(rf"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*{suffix}\b", zone)
        if m:
            return (float(m.group(1)) + float(m.group(2))) / 2, kind
        m = re.search(rf"(\d+(?:\.\d+)?)\s*{suffix}\b", zone)
        if m:
            return float(m.group(1)), kind
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", zone)]
    return (nums[0] if nums else None), "put"


def _zone_strike(zone: str) -> float | None:
    """The strike alone — see _zone_strike_kind."""
    return _zone_strike_kind(zone)[0]


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _zone_expiry(zone: str, today: dt.date) -> dt.date | None:
    """"Oct 16 310P" -> the next Oct 16 on or after today."""
    import re
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", zone, re.I)
    if not m:
        return None
    month, day = _MONTHS[m.group(1).lower()[:3]], int(m.group(2))
    try:
        d = dt.date(today.year, month, day)
    except ValueError:
        return None
    if d < today:
        d = dt.date(today.year + 1, month, day)
    return d


# ---------------------------------------------------------------------------
# grading
# ---------------------------------------------------------------------------

def is_call(p: Pick) -> bool:
    """True for the fade side. Anything not explicitly a call is a put —
    every pick logged before calls were tracked is a short put."""
    return "call" in p.strategy.lower()


def grade_one(p: Pick, label: str, spot_now: float, extreme_since: float | None,
              on: dt.date) -> dict:
    """Grade a short option at a point in time.

    otm        — a put is still OTM above its strike, a call below it
    tested     — price traded through the strike at some point since the pick.
                 For a put that is the lowest low since; for a call the
                 highest high, so `extreme_since` is whichever one applies.
    pct_of_max — share of the original credit the position would show
                 captured if closed now (re-priced with the pick-time IV);
                 this is what the 25/30/50% ladder keys on

    A short call spread is graded on its SHORT leg alone. That overstates
    the loss once price runs past the long strike, so read pct_of_max on a
    spread as a floor, not a mark.
    """
    call = is_call(p)
    exp = dt.date.fromisoformat(p.expiry)
    remaining = max((exp - on).days, 0)
    intrinsic = (max(spot_now - p.strike, 0.0) if call
                 else max(p.strike - spot_now, 0.0))
    if p.mid > 0 and p.iv > 0:
        if remaining == 0:
            mark = intrinsic
        else:
            price = bs.call_price if call else bs.put_price
            try:
                mark = price(spot_now, p.strike, p.iv, remaining / 365.0)
            except ValueError:
                mark = intrinsic
        pct_of_max = (1.0 - mark / p.mid) * 100.0
    else:
        pct_of_max = None
    tested = (extreme_since is not None
              and (extreme_since >= p.strike if call else extreme_since <= p.strike))
    return {
        "on": on.isoformat(),
        "spot": round(spot_now, 2),
        "move_pct": round((spot_now / p.spot - 1.0) * 100.0, 2) if p.spot else None,
        "otm": spot_now < p.strike if call else spot_now > p.strike,
        ("high_since" if call else "low_since"):
            round(extreme_since, 2) if extreme_since is not None else None,
        "tested": tested,
        "pct_of_max": round(pct_of_max, 1) if pct_of_max is not None else None,
        "hit_50": (pct_of_max is not None and pct_of_max >= 50.0),
    }


def due_labels(p: Pick, today: dt.date) -> list[str]:
    picked = dt.date.fromisoformat(p.picked_on)
    exp = dt.date.fromisoformat(p.expiry)
    out = []
    for h in HORIZONS:
        if str(h) not in p.grades and today >= picked + dt.timedelta(days=h) and picked + dt.timedelta(days=h) <= exp:
            out.append(str(h))
    if "expiry" not in p.grades and today >= exp:
        out.append("expiry")
    return out


def due(picks: list[Pick], today: dt.date | None = None) -> dict[str, dict]:
    """{ticker: {"since": earliest picked_on, "labels": [...]}} for every pick
    with a grade outstanding — what a grader needs to go fetch."""
    today = today or dt.date.today()
    out: dict[str, dict] = {}
    for p in picks:
        labels = due_labels(p, today)
        if not labels:
            continue
        d = out.setdefault(p.ticker, {"since": p.picked_on, "labels": []})
        d["since"] = min(d["since"], p.picked_on)
        d["labels"] = sorted(set(d["labels"]) | set(labels))
    return out


def _apply_grades(p: Pick, labels: list[str], spot_now: float,
                  extreme: float | None, today: dt.date) -> int:
    n = 0
    for label in labels:
        on = today if label == "expiry" else dt.date.fromisoformat(p.picked_on) + dt.timedelta(days=int(label))
        on = min(on, today)
        p.grades[label] = grade_one(p, label, spot_now, extreme, on)
        n += 1
    return n


def grade(picks: list[Pick], provider: DataProvider,
          today: dt.date | None = None) -> int:
    """Fill in every grade that has come due, pulling prices from a data
    provider. Returns how many grades were added."""
    today = today or dt.date.today()
    added = 0
    for p in picks:
        labels = due_labels(p, today)
        if not labels:
            continue
        try:
            info = provider.underlying(p.ticker)
            spot_now = info.spot
            since = dt.date.fromisoformat(p.picked_on)
            extreme = (provider.history_highs(p.ticker, since) if is_call(p)
                       else provider.history_lows(p.ticker, since))
        except Exception as exc:
            p.grades.setdefault("error", str(exc))
            continue
        added += _apply_grades(p, labels, spot_now, extreme, today)
    return added


def grade_with_quotes(picks: list[Pick], quotes: dict[str, dict],
                      today: dt.date | None = None) -> int:
    """Same as grade(), but prices come from a caller-supplied
    {ticker: {"spot": x, "low_since": y, "high_since": z}} — for environments
    that can reach a quote feed but not a Python data provider (the scheduled
    routines fetch these from TradingView). Short puts read low_since and
    short calls read high_since; supply whichever the pick needs. Picks whose
    ticker is missing are left for next time."""
    today = today or dt.date.today()
    added = 0
    for p in picks:
        labels = due_labels(p, today)
        q = quotes.get(p.ticker)
        if not labels or not q or q.get("spot") in (None, 0):
            continue
        extreme = q.get("high_since") if is_call(p) else q.get("low_since")
        added += _apply_grades(p, labels, float(q["spot"]),
                               float(extreme) if extreme is not None else None, today)
    return added


# ---------------------------------------------------------------------------
# scorecard
# ---------------------------------------------------------------------------

def scorecard(picks: list[Pick]) -> dict:
    """Aggregate graded picks into the numbers a buyer (or you) would ask for."""
    def rate(items, key):
        vals = [g[key] for g in items if g.get(key) is not None]
        return (100.0 * sum(1 for v in vals if v) / len(vals)) if vals else None

    def avg(items, key):
        vals = [g[key] for g in items if g.get(key) is not None]
        return (sum(vals) / len(vals)) if vals else None

    by_h = {}
    for h in list(map(str, HORIZONS)) + ["expiry"]:
        gs = [p.grades[h] for p in picks if h in p.grades]
        by_h[h] = {"n": len(gs), "otm_pct": rate(gs, "otm"), "tested_pct": rate(gs, "tested"),
                   "hit_50_pct": rate(gs, "hit_50"), "avg_pct_of_max": avg(gs, "pct_of_max")}

    def breakdown(keyfn, h="expiry", fallback="30"):
        groups = defaultdict(list)
        for p in picks:
            g = p.grades.get(h) or p.grades.get(fallback)
            if g:
                for k in keyfn(p):
                    groups[k].append(g)
        return {k: {"n": len(v), "otm_pct": rate(v, "otm"), "tested_pct": rate(v, "tested")}
                for k, v in sorted(groups.items())}

    return {
        "picks": len(picks),
        "graded": sum(1 for p in picks if p.grades),
        "by_horizon": by_h,
        "by_signal": breakdown(lambda p: p.signals or ["(none)"]),
        "by_sector": breakdown(lambda p: [p.sector or "other"]),
        "by_strategy": breakdown(lambda p: [p.strategy or "short put"]),
        "by_source": breakdown(lambda p: [p.source]),
        "tickers": Counter(p.ticker for p in picks).most_common(10),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _provider(source: str):
    if source == "demo":
        from .data import SyntheticProvider
        return SyntheticProvider()
    if source == "tasty":
        from .tastytrade_provider import TastytradeProvider
        return TastytradeProvider()
    from .data import YFinanceProvider
    return YFinanceProvider()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scanner track record")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="log picks")
    r.add_argument("--from-brief", help="brief JSON (brief_pdf schema)")
    r.add_argument("--from-scan", action="store_true", help="run a scan and log its top picks")
    r.add_argument("--source", default="yahoo", choices=["demo", "yahoo", "tasty"])
    r.add_argument("--tags", default="", help="comma-separated universe tags for --from-scan")
    r.add_argument("--path", default=str(DEFAULT_PATH))
    g = sub.add_parser("grade", help="grade every pick that has come due")
    g.add_argument("--source", default="yahoo", choices=["demo", "yahoo", "tasty"])
    g.add_argument("--quotes", help='JSON {ticker: {"spot": x, "low_since": y}} '
                                    "instead of a data provider")
    g.add_argument("--today", help="grade as of this date (YYYY-MM-DD); default today")
    g.add_argument("--path", default=str(DEFAULT_PATH))
    d = sub.add_parser("due", help="list tickers with a grade outstanding (JSON)")
    d.add_argument("--today", help="as of this date (YYYY-MM-DD); default today")
    d.add_argument("--path", default=str(DEFAULT_PATH))
    s = sub.add_parser("show", help="print the scorecard")
    s.add_argument("--path", default=str(DEFAULT_PATH))
    a = ap.parse_args(argv)
    path = pathlib.Path(a.path)
    as_of = dt.date.fromisoformat(a.today) if getattr(a, "today", None) else None

    if a.cmd == "due":
        print(json.dumps(due(load(path), as_of), indent=2))
        return 0

    if a.cmd == "record":
        if a.from_brief:
            picks = picks_from_brief(json.load(open(a.from_brief)))
        elif a.from_scan:
            from .scan import ScanConfig, run_scan
            from .universe import DEFAULT_UNIVERSE, select_by_tags
            uni = select_by_tags(DEFAULT_UNIVERSE, set(t for t in a.tags.split(",") if t)) if a.tags else DEFAULT_UNIVERSE
            res = run_scan(_provider(a.source), uni, ScanConfig())
            picks = picks_from_scan(res, {u.ticker: u.tags for u in uni})
        else:
            ap.error("record needs --from-brief or --from-scan")
        n = record(picks, path)
        print(f"recorded {n} new pick(s) -> {path}")
        for p in picks:
            side = "C" if is_call(p) else "P"
            print(f"  {p.picked_on} {p.ticker:6s} {p.strike:g}{side} exp {p.expiry}  score {p.score:g}")
    elif a.cmd == "grade":
        picks = load(path)
        if a.quotes:
            n = grade_with_quotes(picks, json.load(open(a.quotes)), as_of)
        else:
            n = grade(picks, _provider(a.source), as_of)
        save(picks, path)
        print(f"graded {n} horizon(s) across {len(picks)} pick(s)")
    else:
        sc = scorecard(load(path))
        print(json.dumps(sc, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
