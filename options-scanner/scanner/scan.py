"""Scan orchestration: sweep the universe, build candidates, score and rank."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .data import DataProvider, UnderlyingInfo
from .strategies import (BrokenWingButterfly, CashSecuredPut, IronCondor,
                         build_bwb, build_csps, build_iron_condor)
from .universe import Symbol


@dataclass
class ScanConfig:
    min_dte: int = 7
    max_dte: int = 45
    # CSP / wheel
    delta_min: float = 0.10
    delta_max: float = 0.35
    min_annualized_pct: float = 12.0
    min_open_interest: int = 100
    max_spread_pct: float = 0.25
    min_premium: float = 0.10
    max_capital: float | None = None      # skip strikes needing more cash than this
    avoid_earnings: bool = True           # penalize (not drop) earnings-before-expiry
    # Spreads
    condor_short_delta: float = 0.16
    condor_width_pct: float = 0.02
    bwb_body_delta: float = 0.30
    max_workers: int = 8


@dataclass
class ScanResult:
    infos: dict[str, UnderlyingInfo] = field(default_factory=dict)
    csps: list[CashSecuredPut] = field(default_factory=list)
    condors: list[IronCondor] = field(default_factory=list)
    bwbs: list[BrokenWingButterfly] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def _target_expiries(info: UnderlyingInfo, cfg: ScanConfig) -> list[dt.date]:
    today = dt.date.today()
    in_window = [e for e in info.expiries
                 if cfg.min_dte <= (e - today).days <= cfg.max_dte]
    # cap per-ticker fetches: nearest, middle, farthest expiry in window
    if len(in_window) > 3:
        in_window = [in_window[0], in_window[len(in_window) // 2], in_window[-1]]
    return in_window


def _earnings_before(info: UnderlyingInfo, expiry: dt.date) -> bool:
    return info.next_earnings is not None and info.next_earnings <= expiry


def _atm_iv(chain) -> float:
    """Average IV of the two strikes nearest spot — the chain's own read on
    volatility for this expiry, used for the expected move when the
    provider doesn't supply one."""
    cands = [q for q in chain.puts + chain.calls if q.iv > 0]
    if not cands:
        return 0.0
    near = sorted(cands, key=lambda q: abs(q.strike - chain.spot))[:2]
    return sum(q.iv for q in near) / len(near)


def _scan_one(provider: DataProvider, ticker: str, cfg: ScanConfig) -> ScanResult:
    """Everything for one symbol, returned as a mini-result so workers never
    touch shared state."""
    from . import bs
    from .futures import product_for

    part = ScanResult()
    info = provider.underlying(ticker)
    part.infos[ticker] = info
    prod = product_for(ticker)
    margin = prod.margin_estimate if prod else None
    for expiry in _target_expiries(info, cfg):
        chain = provider.chain(ticker, expiry)
        earn = _earnings_before(info, expiry)
        iv_exp = provider.expiry_iv(ticker, expiry) or _atm_iv(chain)
        em = bs.expected_move(chain.spot, iv_exp, chain.dte) if iv_exp else None
        part.csps.extend(build_csps(
            chain, earnings_before_expiry=earn,
            delta_range=(cfg.delta_min, cfg.delta_max),
            min_open_interest=cfg.min_open_interest,
            max_spread_pct=cfg.max_spread_pct,
            min_premium=cfg.min_premium,
            entry_signals=info.entry_signals,
            margin_estimate=margin, rsi_14=info.rsi_14,
            expected_move=em, iv_rank=info.iv_rank,
            dividend_yield=info.dividend_yield))
        ic = build_iron_condor(
            chain, short_delta=cfg.condor_short_delta,
            width_pct=cfg.condor_width_pct,
            min_open_interest=cfg.min_open_interest,
            earnings_before_expiry=earn)
        if ic:
            part.condors.append(ic)
        fly = build_bwb(
            chain, body_delta=cfg.bwb_body_delta,
            min_open_interest=max(cfg.min_open_interest // 2, 25),
            earnings_before_expiry=earn)
        if fly:
            part.bwbs.append(fly)
    return part


def run_scan(provider: DataProvider, universe: list[Symbol],
             cfg: ScanConfig | None = None,
             progress=None) -> ScanResult:
    """Sweep every symbol, `cfg.max_workers` at a time. `progress` is an
    optional callback(i, n, ticker), invoked on the calling thread as each
    symbol finishes (so it is safe to drive a Streamlit progress bar)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cfg = cfg or ScanConfig()
    result = ScanResult()
    tags = {s.ticker: s.tags for s in universe}
    tickers = [s.ticker for s in universe]

    try:                       # one bulk market-metrics call, when supported
        provider.prefetch(tickers)
    except Exception:
        pass

    parts: dict[str, ScanResult] = {}
    workers = max(1, min(cfg.max_workers, len(tickers) or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_scan_one, provider, t, cfg): t for t in tickers}
        for done, fut in enumerate(as_completed(futs)):
            t = futs[fut]
            if progress:
                progress(done, len(tickers), t)
            try:
                parts[t] = fut.result()
            except Exception as exc:  # a bad ticker must never kill the scan
                result.errors[t] = str(exc)

    for t in tickers:          # keep universe order so output is deterministic
        p = parts.get(t)
        if p is None:
            continue
        result.infos.update(p.infos)
        result.csps.extend(p.csps)
        result.condors.extend(p.condors)
        result.bwbs.extend(p.bwbs)

    if cfg.max_capital is not None:
        result.csps = [c for c in result.csps if c.capital <= cfg.max_capital]
    result.csps = [c for c in result.csps if c.annualized_pct >= cfg.min_annualized_pct]

    result.csps.sort(key=lambda c: score_csp(c, tags.get(c.ticker, frozenset()), cfg), reverse=True)
    result.condors.sort(key=lambda c: score_condor(c, cfg), reverse=True)
    result.bwbs.sort(key=lambda b: score_bwb(b, cfg), reverse=True)
    return result


def dedupe_csps(csps: list[CashSecuredPut], per_expiry: int = 1) -> list[CashSecuredPut]:
    """Collapse the strike ladder: keep the top `per_expiry` strikes per
    (ticker, expiry). The scanner naturally emits every strike in the delta
    band — eight /ES rows at one expiry is one trade idea, not eight.
    Assumes `csps` is already sorted best-first."""
    counts: dict[tuple, int] = {}
    out = []
    for c in csps:
        key = (c.ticker, c.expiry)
        n = counts.get(key, 0)
        if n < per_expiry:
            out.append(c)
            counts[key] = n + 1
    return out


# ---------------------------------------------------------------------------
# Scoring — a single 0-100 number so "best trades today" means something.
# ---------------------------------------------------------------------------

def score_csp(c: CashSecuredPut, tags: frozenset, cfg: ScanConfig) -> float:
    """Balance yield against safety and quality. Yield alone would rank the
    junkiest names first; this is a wheel scanner, not a lottery scanner."""
    yield_score = min(c.annualized_pct / 60.0, 1.0) * 40.0        # 40 pts: annualized ROC, caps at 60%
    safety = (c.prob_otm_pct / 100.0) * 25.0                       # 25 pts: prob of keeping premium
    protection = min(c.downside_protection_pct / 15.0, 1.0) * 15.0  # 15 pts: cushion
    liquidity = min(c.open_interest / 2000.0, 1.0) * 10.0          # 10 pts
    quality = 10.0 if ("blue-chip" in tags or "etf" in tags) else 4.0
    # Technical entry bonus: oversold RSI, lower Bollinger touch, 50-SMA
    # support each add 6 pts — a washed-out quality name beats a random one
    # at the same yield.
    entry = min(len(c.entry_signals), 3) * 6.0
    score = yield_score + safety + protection + liquidity + quality + entry
    # v2 — volatility context. Premium is only "rich" relative to the name's
    # own history: up to 10 pts for IV rank, and a penalty when IVR is under
    # 20 (cheap premium usually means IV is about to expand against you).
    # Both terms are silent when the provider has no IV data.
    if c.iv_rank is not None:
        ivr = min(max(c.iv_rank, 0.0), 100.0)
        score += ivr / 100.0 * 10.0
        if ivr < 20.0:
            score -= 8.0
    # v2 — strike placement. Outside one expected move is the professional
    # default; reward it, and give partial credit for 0.7+ EM.
    cushion = c.em_cushion
    if cushion is not None:
        score += 6.0 if cushion >= 1.0 else (3.0 if cushion >= 0.7 else 0.0)
    if c.earnings_before_expiry and cfg.avoid_earnings:
        score -= 20.0
    if c.spread_pct > 0.12:
        score -= 5.0
    return round(max(score, 0.0), 1)


def score_condor(c: IronCondor, cfg: ScanConfig) -> float:
    rr = min(c.roc_pct / 50.0, 1.0) * 40.0     # credit vs max loss, caps at 50% ROC
    pop = (c.pop_pct / 100.0) * 40.0
    liquidity = min(c.min_open_interest / 1000.0, 1.0) * 20.0
    score = rr + pop + liquidity
    if c.earnings_before_expiry and cfg.avoid_earnings:
        score -= 20.0
    return round(max(score, 0.0), 1)


def score_bwb(b: BrokenWingButterfly, cfg: ScanConfig) -> float:
    credit_bonus = 25.0 if b.net_credit > 0 else 0.0   # no-upside-risk flies favored
    pop = (b.pop_pct / 100.0) * 40.0
    rr = min(b.roc_pct / 100.0, 1.0) * 20.0 if b.max_loss > 0 else 20.0
    liquidity = min(b.min_open_interest / 500.0, 1.0) * 15.0
    score = credit_bonus + pop + rr + liquidity
    if b.earnings_before_expiry and cfg.avoid_earnings:
        score -= 20.0
    return round(max(score, 0.0), 1)


# ---------------------------------------------------------------------------
# "Quality names down the most" — wheel entry radar.
# ---------------------------------------------------------------------------

@dataclass
class DipCandidate:
    ticker: str
    spot: float
    day_change_pct: float
    pct_off_52w_high: float
    rsi_14: float
    tags: frozenset
    next_earnings: dt.date | None
    entry_signals: frozenset = frozenset()
    sma_50: float = 0.0
    boll_lower: float = 0.0

    @property
    def dip_score(self) -> float:
        """Bigger = more washed out. Day drop + distance off high + oversold
        RSI, plus a bonus per technical entry signal (RSI<=30 / LowerBB / 50SMA)."""
        day = max(-self.day_change_pct, 0.0) * 3.0
        off_high = max(-self.pct_off_52w_high, 0.0) * 0.8
        oversold = max(40.0 - self.rsi_14, 0.0) * 1.2
        signals = len(self.entry_signals) * 10.0
        return round(day + off_high + oversold + signals, 1)


def rank_dips(infos: dict[str, UnderlyingInfo], universe: list[Symbol],
              quality_only: bool = True) -> list[DipCandidate]:
    tags = {s.ticker: s.tags for s in universe}
    out = []
    for tk, info in infos.items():
        t = tags.get(tk, frozenset())
        if quality_only and not ({"blue-chip", "etf", "dividend"} & t):
            continue
        out.append(DipCandidate(tk, info.spot, info.day_change_pct,
                                info.pct_off_52w_high, info.rsi_14, t,
                                info.next_earnings, info.entry_signals,
                                info.sma_50, info.boll_lower))
    out.sort(key=lambda d: d.dip_score, reverse=True)
    return out
