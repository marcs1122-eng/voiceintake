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
    strategy: str             # "short put" (the only graded strategy for now)
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
        return (self.picked_on, self.ticker, self.strike, self.expiry)

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
    strike zone like "Sell 125P" or "172-177P"; we log the named strike (or
    the midpoint of a range) with a nominal 45-day expiry so the pick can
    still be graded on direction and drawdown."""
    import re
    today = today or dt.date.today()
    out = []
    for c in brief.get("candidates", []):
        zone = str(c.get("zone", ""))
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", zone)]
        if not nums or not c.get("spot"):
            continue
        strike = sum(nums[:2]) / len(nums[:2])
        spot = float(str(c["spot"]).replace(",", ""))
        rsi = float(c["rsi"]) if c.get("rsi") not in (None, "") else None
        out.append(Pick(
            picked_on=today.isoformat(), ticker=str(c["ticker"]).upper(),
            strategy="short put", strike=strike,
            expiry=(today + dt.timedelta(days=45)).isoformat(), dte=45,
            spot=spot, mid=0.0, rsi=rsi,
            signals=[s.strip() for s in str(c.get("signals", "")).split("·") if s.strip()],
            source="brief"))
    return out


# ---------------------------------------------------------------------------
# grading
# ---------------------------------------------------------------------------

def grade_one(p: Pick, label: str, spot_now: float, low_since: float | None,
              on: dt.date) -> dict:
    """Grade a short put at a point in time.

    otm        — spot is still above the strike
    tested     — price traded through the strike at some point since the pick
    pct_of_max — share of the original credit the position would show
                 captured if closed now (re-priced with the pick-time IV);
                 this is what the 25/30/50% ladder keys on
    """
    exp = dt.date.fromisoformat(p.expiry)
    remaining = max((exp - on).days, 0)
    if p.mid > 0 and p.iv > 0:
        if remaining == 0:
            mark = max(p.strike - spot_now, 0.0)
        else:
            try:
                mark = bs.put_price(spot_now, p.strike, p.iv, remaining / 365.0)
            except ValueError:
                mark = max(p.strike - spot_now, 0.0)
        pct_of_max = (1.0 - mark / p.mid) * 100.0
    else:
        pct_of_max = None
    return {
        "on": on.isoformat(),
        "spot": round(spot_now, 2),
        "move_pct": round((spot_now / p.spot - 1.0) * 100.0, 2) if p.spot else None,
        "otm": spot_now > p.strike,
        "low_since": round(low_since, 2) if low_since is not None else None,
        "tested": (low_since is not None and low_since <= p.strike),
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


def grade(picks: list[Pick], provider: DataProvider,
          today: dt.date | None = None) -> int:
    """Fill in every grade that has come due. Returns how many were added."""
    today = today or dt.date.today()
    added = 0
    for p in picks:
        labels = due_labels(p, today)
        if not labels:
            continue
        try:
            info = provider.underlying(p.ticker)
            spot_now = info.spot
            low = provider.history_lows(p.ticker, dt.date.fromisoformat(p.picked_on))
        except Exception as exc:
            p.grades.setdefault("error", str(exc))
            continue
        for label in labels:
            on = today if label == "expiry" else dt.date.fromisoformat(p.picked_on) + dt.timedelta(days=int(label))
            on = min(on, today)
            p.grades[label] = grade_one(p, label, spot_now, low, on)
            added += 1
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
    g.add_argument("--path", default=str(DEFAULT_PATH))
    s = sub.add_parser("show", help="print the scorecard")
    s.add_argument("--path", default=str(DEFAULT_PATH))
    a = ap.parse_args(argv)
    path = pathlib.Path(a.path)

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
            print(f"  {p.picked_on} {p.ticker:6s} {p.strike:g}P exp {p.expiry}  score {p.score:g}")
    elif a.cmd == "grade":
        picks = load(path)
        n = grade(picks, _provider(a.source))
        save(picks, path)
        print(f"graded {n} horizon(s) across {len(picks)} pick(s)")
    else:
        sc = scorecard(load(path))
        print(json.dumps(sc, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
