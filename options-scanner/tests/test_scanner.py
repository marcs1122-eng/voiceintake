"""Tests for the options scanner math and strategy builders.

Run from options-scanner/:  python -m pytest tests/ -q
"""

import datetime as dt
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import bs
from scanner.data import ChainSnapshot, OptionQuote, SyntheticProvider
from scanner.scan import ScanConfig, rank_dips, run_scan
from scanner.strategies import build_bwb, build_csps, build_iron_condor
from scanner.universe import DEFAULT_UNIVERSE, filter_universe


# ---------------------------------------------------------------------------
# Black-Scholes
# ---------------------------------------------------------------------------

def test_put_call_parity():
    s, k, iv, t, r = 100.0, 95.0, 0.3, 0.25, 0.04
    c = bs.call_price(s, k, iv, t, r)
    p = bs.put_price(s, k, iv, t, r)
    assert c - p == pytest.approx(s - k * math.exp(-r * t), abs=1e-9)


def test_atm_put_delta_near_half():
    d = bs.put_delta(100, 100, 0.3, 30 / 365)
    assert -0.55 < d < -0.40


def test_deep_otm_put_delta_small():
    assert abs(bs.put_delta(100, 60, 0.3, 30 / 365)) < 0.02


def test_prob_below_above_sum_to_one():
    pb = bs.prob_below(100, 95, 0.4, 0.1)
    pa = bs.prob_above(100, 95, 0.4, 0.1)
    assert pb + pa == pytest.approx(1.0)
    assert 0 < pb < 0.5  # below-spot level is less likely than not


def test_bs_rejects_bad_inputs():
    with pytest.raises(ValueError):
        bs.put_delta(100, 100, 0.0, 0.1)


# ---------------------------------------------------------------------------
# Chain fixture
# ---------------------------------------------------------------------------

def _chain(spot=100.0, dte=30, iv=0.35) -> ChainSnapshot:
    expiry = dt.date.today() + dt.timedelta(days=dte)
    t = dte / 365.0
    puts, calls = [], []
    for k in range(60, 141, 5):
        p = bs.put_price(spot, k, iv, t)
        c = bs.call_price(spot, k, iv, t)
        puts.append(OptionQuote(k, max(p - 0.05, 0), p + 0.05, iv, 5000, 500))
        calls.append(OptionQuote(k, max(c - 0.05, 0), c + 0.05, iv, 5000, 500))
    return ChainSnapshot("TEST", spot, expiry, puts, calls)


# ---------------------------------------------------------------------------
# Cash-secured puts
# ---------------------------------------------------------------------------

def test_csp_basic_metrics():
    csps = build_csps(_chain())
    assert csps, "expected OTM put candidates"
    for c in csps:
        assert c.strike < c.spot
        assert 0.10 <= abs(c.delta) <= 0.40
        assert c.capital == c.strike * 100
        assert c.breakeven == pytest.approx(c.strike - c.mid)
        assert c.roc_pct == pytest.approx(c.mid / c.strike * 100)
        assert c.annualized_pct == pytest.approx(c.roc_pct * 365 / c.dte)
        assert 0 <= c.prob_otm_pct <= 100
        assert c.downside_protection_pct > c.otm_pct  # premium adds cushion


def test_csp_filters_illiquid():
    ch = _chain()
    for q in ch.puts:
        q.open_interest = 5
    assert build_csps(ch) == []


# ---------------------------------------------------------------------------
# Iron condor
# ---------------------------------------------------------------------------

def test_condor_structure_and_payoff():
    ic = build_iron_condor(_chain(), short_delta=0.20, width_pct=0.05)
    assert ic is not None
    assert ic.put_long < ic.put_short < ic.spot < ic.call_short < ic.call_long
    assert ic.credit > 0
    assert ic.max_loss > 0
    assert ic.max_loss == pytest.approx(ic.width - ic.credit)
    assert ic.breakeven_low < ic.put_short
    assert ic.breakeven_high > ic.call_short
    assert 0 < ic.pop_pct < 100
    # short strikes actually near target delta
    assert abs(abs(ic.put_short_delta) - 0.20) < 0.12
    assert abs(ic.call_short_delta - 0.20) < 0.12


def test_condor_none_when_chain_too_thin():
    expiry = dt.date.today() + dt.timedelta(days=30)
    ch = ChainSnapshot("X", 100, expiry,
                       [OptionQuote(95, 1, 1.1, 0.3, 500, 10)],
                       [OptionQuote(105, 1, 1.1, 0.3, 500, 10)])
    assert build_iron_condor(ch) is None


# ---------------------------------------------------------------------------
# Broken wing butterfly
# ---------------------------------------------------------------------------

def test_bwb_structure():
    fly = build_bwb(_chain(spot=100, iv=0.45))
    assert fly is not None
    assert fly.long_low < fly.short_mid < fly.long_high <= fly.spot
    assert fly.lower_width > fly.upper_width  # wing is actually broken
    # payoff identities
    assert fly.max_profit == pytest.approx(fly.upper_width + fly.net_credit)
    assert fly.max_loss == pytest.approx(
        (fly.lower_width - fly.upper_width) - fly.net_credit)
    assert fly.breakeven_low == pytest.approx(
        2 * fly.short_mid - fly.long_high - fly.net_credit)


def test_bwb_payoff_at_expiry_matches_formulas():
    fly = build_bwb(_chain(spot=100, iv=0.45))
    assert fly is not None

    def payoff(s):
        legs = (max(fly.long_low - s, 0) - 2 * max(fly.short_mid - s, 0)
                + max(fly.long_high - s, 0))
        return legs + fly.net_credit

    assert payoff(fly.short_mid) == pytest.approx(fly.max_profit)
    assert payoff(0.01) == pytest.approx(-fly.max_loss, abs=0.02)
    assert payoff(fly.breakeven_low) == pytest.approx(0, abs=0.01)
    # entered for a credit → no loss to the upside
    if fly.net_credit > 0:
        assert payoff(fly.spot * 2) == pytest.approx(fly.net_credit)


# ---------------------------------------------------------------------------
# Full scan on synthetic data
# ---------------------------------------------------------------------------

def test_full_demo_scan():
    provider = SyntheticProvider(seed=7)
    universe = DEFAULT_UNIVERSE[:12]
    cfg = ScanConfig(min_annualized_pct=5.0)
    result = run_scan(provider, universe, cfg)
    assert not result.errors
    assert result.infos
    assert result.csps
    # ranked by score: spot-check ordering is descending
    from scanner.scan import score_csp
    tags = {s.ticker: s.tags for s in universe}
    scores = [score_csp(c, tags.get(c.ticker, frozenset()), cfg) for c in result.csps]
    assert scores == sorted(scores, reverse=True)
    dips = rank_dips(result.infos, universe)
    assert dips
    assert dips[0].dip_score >= dips[-1].dip_score


def test_max_capital_filter():
    provider = SyntheticProvider(seed=7)
    cfg = ScanConfig(min_annualized_pct=0.0, max_capital=10_000)
    result = run_scan(provider, DEFAULT_UNIVERSE[:12], cfg)
    assert all(c.capital <= 10_000 for c in result.csps)


def test_entry_signals():
    from scanner.data import UnderlyingInfo

    base = dict(ticker="X", day_change_pct=0.0, pct_off_52w_high=-5.0,
                hist_vol_20d=0.3, next_earnings=None, expiries=[])
    # oversold + at lower band + at 50-SMA support
    hot = UnderlyingInfo(spot=100.0, rsi_14=28.0, sma_50=99.5,
                         boll_lower=101.0, boll_upper=115.0, **base)
    assert hot.entry_signals == {"RSI<=30", "LowerBB", "50SMA"}
    # nothing triggered: RSI high, far above band and SMA
    cold = UnderlyingInfo(spot=100.0, rsi_14=60.0, sma_50=80.0,
                          boll_lower=90.0, boll_upper=110.0, **base)
    assert cold.entry_signals == frozenset()
    # below the SMA band (broken support) does not count as 50SMA
    below = UnderlyingInfo(spot=100.0, rsi_14=60.0, sma_50=105.0,
                           boll_lower=90.0, boll_upper=110.0, **base)
    assert "50SMA" not in below.entry_signals


def test_entry_signals_boost_csp_score():
    from scanner.scan import score_csp
    cfg = ScanConfig()
    csps = build_csps(_chain(), entry_signals=frozenset())
    assert csps
    plain = csps[0]
    boosted = build_csps(_chain(), entry_signals=frozenset({"RSI<=30", "LowerBB"}))[0]
    assert score_csp(boosted, frozenset(), cfg) == pytest.approx(
        score_csp(plain, frozenset(), cfg) + 12.0)


def test_implied_vol_roundtrip():
    s, k, t = 100.0, 92.0, 30 / 365
    for true_iv in (0.15, 0.35, 0.80):
        price = bs.put_price(s, k, true_iv, t)
        assert bs.implied_vol(price, s, k, t, is_put=True) == pytest.approx(true_iv, abs=0.002)
    assert bs.implied_vol(0.0, s, k, t) == 0.0
    assert bs.implied_vol(0.001, s, 200.0, t) == 0.0  # below intrinsic → stale quote


def test_futures_csp_uses_margin_and_multiplier():
    from scanner.strategies import CashSecuredPut
    # /ES-style: 50x multiplier, $17k margin, 40-point-OTM put at 30.0 mid
    c = CashSecuredPut(ticker="/ES", spot=5000.0, expiry=dt.date.today() + dt.timedelta(days=30),
                       dte=30, strike=4900.0, bid=29.0, mid=30.0, iv=0.2, delta=-0.25,
                       open_interest=5000, volume=100, spread_pct=0.05,
                       earnings_before_expiry=False, multiplier=50.0,
                       margin_estimate=17_000.0)
    assert c.is_futures
    assert c.premium == 1500.0            # 30.0 * $50
    assert c.capital == 17_000.0          # margin, not strike*mult
    assert c.roc_pct == pytest.approx(1500 / 17_000 * 100)
    # equity behavior unchanged
    e = CashSecuredPut(ticker="KO", spot=60.0, expiry=c.expiry, dte=30, strike=57.5,
                       bid=0.5, mid=0.55, iv=0.2, delta=-0.25, open_interest=5000,
                       volume=100, spread_pct=0.05, earnings_before_expiry=False)
    assert e.capital == 5750.0 and e.premium == pytest.approx(55.0)


def test_synthetic_futures_scan():
    from scanner.data import SyntheticProvider
    from scanner.universe import filter_universe
    provider = SyntheticProvider(seed=7)
    futs = filter_universe(DEFAULT_UNIVERSE, include_tags={"futures"})[:4]
    result = run_scan(provider, futs, ScanConfig(min_annualized_pct=0.0))
    assert not result.errors
    fut_csps = [c for c in result.csps if c.ticker.startswith("/")]
    assert fut_csps
    from scanner.futures import product_for
    for c in fut_csps:
        prod = product_for(c.ticker)
        assert c.multiplier == prod.multiplier
        assert c.capital == prod.margin_estimate


def test_day_low_high_flags():
    from scanner.data import UnderlyingInfo

    base = dict(ticker="X", day_change_pct=0.0, pct_off_52w_high=-5.0,
                hist_vol_20d=0.3, rsi_14=50.0, next_earnings=None, expiries=[])
    at_low = UnderlyingInfo(spot=100.0, day_low=99.8, day_high=104.0, **base)
    assert at_low.at_day_low and not at_low.at_day_high
    at_high = UnderlyingInfo(spot=103.9, day_low=99.8, day_high=104.0, **base)
    assert at_high.at_day_high and not at_high.at_day_low
    mid = UnderlyingInfo(spot=102.0, day_low=99.8, day_high=104.0, **base)
    assert not mid.at_day_low and not mid.at_day_high
    unknown = UnderlyingInfo(spot=102.0, **base)  # no session data yet
    assert not unknown.at_day_low and not unknown.at_day_high


def test_rsi_carried_onto_puts():
    from scanner.data import SyntheticProvider
    provider = SyntheticProvider(seed=7)
    universe = DEFAULT_UNIVERSE[:6]
    result = run_scan(provider, universe, ScanConfig(min_annualized_pct=0.0))
    assert result.csps
    for c in result.csps:
        assert c.rsi_14 == result.infos[c.ticker].rsi_14


def test_providers_accept_timeframe():
    from scanner.data import SyntheticProvider, TIMEFRAMES
    assert set(TIMEFRAMES) == {"5m", "10m", "1h", "4h", "1d"}
    p = SyntheticProvider(timeframe="5m")
    assert p.timeframe == "5m"
    assert p.underlying("SPY").spot > 0  # synthetic ignores timeframe but still works


def test_position_suggestions():
    from scanner.tastytrade_provider import position_suggestion

    # Mac's ladder: 25% day one, 30% day two, then 50% / 21 DTE
    assert "day-1" in position_suggestion(26.0, 40, True, days_held=0)
    assert position_suggestion(20.0, 40, True, days_held=0) == "hold"
    assert "day-2" in position_suggestion(31.0, 40, True, days_held=1)
    assert position_suggestion(31.0, 40, True, days_held=5) == "hold"  # 31% later: wait for 50
    assert "50% rule" in position_suggestion(62.0, 30, True, days_held=10)
    assert "CLOSE" in position_suggestion(62.0, 30, True)          # unknown open date → 50% rule
    assert "TESTED" in position_suggestion(-15.0, 30, True, days_held=0)
    assert position_suggestion(-3.0, 40, True, days_held=2) == "hold"  # few cents against = noise
    assert "21-DTE" in position_suggestion(20.0, 14, True, days_held=10)
    assert position_suggestion(20.0, 35, True, days_held=10) == "hold"
    assert position_suggestion(None, 5, True) == ""                # no data
    assert position_suggestion(80.0, 5, False) == ""               # long position


def test_pretty_symbol():
    from scanner.tastytrade_provider import pretty_symbol

    assert pretty_symbol("NFLX  261120C00085000") == "NFLX 11/20/26 $85 CALL"
    assert pretty_symbol("QQQ   261016P00700000") == "QQQ 10/16/26 $700 PUT"
    assert pretty_symbol("./6EZ6 EUUV6 261009P1.15") == "/6EZ6 10/09/26 $1.15 PUT"
    assert pretty_symbol("AAPL") == "AAPL"  # stock: unchanged


def test_correlation_analysis():
    import numpy as np
    import pandas as pd
    from scanner import correlation as cm

    rng = np.random.default_rng(7)
    base = rng.normal(0, 1, 80)
    closes = pd.DataFrame({
        "A": 100 * np.cumprod(1 + base * 0.01),
        "B": 100 * np.cumprod(1 + (base * 0.9 + rng.normal(0, 0.3, 80)) * 0.01),  # tracks A
        "C": 100 * np.cumprod(1 + rng.normal(0, 1, 80) * 0.01),                    # independent
    })
    m = cm.corr_matrix(closes)
    stats = cm.analyze(m)
    assert m.loc["A", "B"] >= 0.7                       # the clone pair is hot
    assert ("A", "B", m.loc["A", "B"]) in [(a, b, c) for a, b, c in stats["hot_pairs"]] or \
           stats["hot_pairs"][0][:2] == ("A", "B")
    assert abs(m.loc["A", "C"]) < 0.5                   # independent stays cool
    top = next(iter(stats["avg_by_symbol"]))
    assert top in ("A", "B")                            # clones lead the avg ranking
    assert "🟢" in cm.rate_portfolio(0.1) and "🔴" in cm.rate_portfolio(0.7)


def test_yahoo_symbol_mapping():
    from scanner.correlation import yahoo_symbol_for
    assert yahoo_symbol_for("/ES") == "ES=F"
    assert yahoo_symbol_for("NDXP") == "^NDX"
    assert yahoo_symbol_for("SPXW") == "^SPX"
    assert yahoo_symbol_for("AAPL") == "AAPL"
    assert yahoo_symbol_for("/6E") == "6E=F"


def test_sector_tags_are_equities_only():
    futs = filter_universe(DEFAULT_UNIVERSE, include_tags={"futures"})
    sector_tags = {"tech", "semis", "financials", "healthcare", "consumer",
                   "industrials", "energy", "materials", "utilities", "reits", "china"}
    for f in futs:
        assert not (f.tags & sector_tags), f"{f.ticker} carries a sector tag"
    # memory/semi additions present
    semis = {s.ticker for s in filter_universe(DEFAULT_UNIVERSE, include_tags={"semis"})}
    for t in ("WDC", "STX", "MU", "ASML", "MRVL"):
        assert t in semis


def test_universe_filters():
    etfs = filter_universe(DEFAULT_UNIVERSE, include_tags={"etf"})
    assert etfs and all(s.has("etf") for s in etfs)
    no_etfs = filter_universe(DEFAULT_UNIVERSE, exclude_tags={"etf"})
    assert no_etfs and not any(s.has("etf") for s in no_etfs)
    picks = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL"})
    assert {s.ticker for s in picks} == {"SPY", "AAPL"}


def test_futures_registry_sane():
    from scanner.futures import FUTURES_PRODUCTS, product_for

    syms = [p.symbol for p in FUTURES_PRODUCTS]
    assert len(syms) == len(set(syms)), "duplicate futures symbols"
    for p in FUTURES_PRODUCTS:
        assert p.symbol.startswith("/")
        assert p.multiplier > 0 and p.margin_estimate > 0
        assert p.tier in (1, 2, 3)
        assert -1.0 <= p.corr_es <= 1.0
        assert p.group
    # micros must be smaller than their full-size sibling
    for micro, full in (("/MES", "/ES"), ("/MNQ", "/NQ"), ("/MCL", "/CL"),
                        ("/MGC", "/GC"), ("/M2K", "/RTY"), ("/SIL", "/SI")):
        m, f = product_for(micro), product_for(full)
        assert m.multiplier < f.multiplier and m.margin_estimate < f.margin_estimate
    # the products we deliberately excluded stay out
    for excluded in ("/SR3", "/BTC", "/ETH"):
        assert product_for(excluded) is None


def test_uncorrelated_tag_matches_registry():
    from scanner.futures import product_for
    from scanner.universe import DEFAULT_UNIVERSE

    for sym in DEFAULT_UNIVERSE:
        prod = product_for(sym.ticker)
        if prod is None:
            continue
        expect = abs(prod.corr_es) <= 0.20
        assert sym.has("uncorrelated") == expect, f"{sym.ticker} uncorrelated tag wrong"


# ---------------------------------------------------------------------------
# Sector scans stay equities-only; futures need an explicit futures tag
# ---------------------------------------------------------------------------

def test_sector_tags_exclude_futures():
    from scanner.universe import select_by_tags

    energy = select_by_tags(DEFAULT_UNIVERSE, {"energy"})
    assert energy and not any(s.ticker.startswith("/") for s in energy)
    # a shared style tag must not drag futures in either
    mixed = select_by_tags(DEFAULT_UNIVERSE, {"energy", "high-iv"})
    assert mixed and not any(s.ticker.startswith("/") for s in mixed)
    # but an explicit futures tag still works
    fut_energy = select_by_tags(DEFAULT_UNIVERSE, {"fut-energy"})
    assert fut_energy and all(s.ticker.startswith("/") for s in fut_energy)
    assert "/CL" in {s.ticker for s in fut_energy}


def test_dedupe_csps_collapses_strike_ladder():
    from scanner.scan import dedupe_csps

    cfg = ScanConfig(min_dte=0, max_dte=60, min_annualized_pct=0.0)
    provider = SyntheticProvider()
    universe = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL"})
    result = run_scan(provider, universe, cfg)
    assert result.csps, "need candidates to dedupe"
    best = dedupe_csps(result.csps)
    keys = [(c.ticker, c.expiry) for c in best]
    assert len(keys) == len(set(keys)), "still more than one strike per ticker+expiry"
    # order preserved and the kept row is the top-scored one for its key
    first_by_key = {}
    for c in result.csps:
        first_by_key.setdefault((c.ticker, c.expiry), c)
    for c in best:
        assert c is first_by_key[(c.ticker, c.expiry)]
    assert dedupe_csps(result.csps, per_expiry=2)
    assert len(dedupe_csps(result.csps, per_expiry=2)) >= len(best)


# ---------------------------------------------------------------------------
# Futures scalp radar
# ---------------------------------------------------------------------------

def _flat_bars(price=100.0, n=60):
    return [(price + 0.1, price - 0.1, price) for _ in range(n)]


def test_scalp_long_setup_at_washed_out_low():
    from scanner.scalp import analyze

    # downtrend into the session low: RSI pinned, below the lower band
    bars = []
    price = 7700.0
    for i in range(60):
        price -= 3.0
        bars.append((price + 2.0, price - 1.0, price))
    spot = price
    setup = analyze("/ES", bars, spot, day_low=spot, day_high=7700.0)
    assert setup.bias == "LONG SCALP"
    assert setup.rsi <= 30
    assert "at day low" in setup.signals
    assert setup.stop is not None and setup.stop < spot
    assert setup.target is not None and setup.target > spot   # mean is above
    assert setup.risk_dollars and setup.risk_dollars > 0
    assert setup.per_point == 50.0 and setup.micro == "/MES"


def test_scalp_short_setup_at_blown_out_high():
    from scanner.scalp import analyze

    bars = []
    price = 85.0
    for i in range(60):
        price += 0.10
        bars.append((price + 0.05, price - 0.02, price))
    spot = price
    setup = analyze("/CL", bars, spot, day_low=85.0, day_high=spot)
    assert setup.bias == "SHORT SCALP"
    assert setup.stop is not None and setup.stop > spot
    assert setup.target is not None and setup.target < spot


def test_scalp_no_edge_mid_range():
    from scanner.scalp import analyze

    setup = analyze("/GC", _flat_bars(4400.0), 4400.0,
                    day_low=4390.0, day_high=4410.0)
    assert setup.bias == "no edge"
    assert setup.stop is None and setup.target is None
    assert setup.range_pos_pct == pytest.approx(50.0)


def test_scalp_needs_enough_bars():
    from scanner.scalp import analyze

    with pytest.raises(ValueError):
        analyze("/ES", _flat_bars(n=10), 100.0)


def test_scalp_demo_scan_runs_offline():
    from scanner.scalp import SCALP_FUTURES, run_scalp_scan

    rows, errors = run_scalp_scan("5m", source="demo")
    assert not errors
    assert {r.ticker for r in rows} == set(SCALP_FUTURES)
    for r in rows:
        assert r.atr > 0 and r.per_point > 0
        assert r.bias in ("LONG SCALP", "SHORT SCALP",
                          "lean long", "lean short", "no edge")
    # actionable setups sort to the top
    order = [r.bias for r in rows]
    seen_idle = False
    for b in order:
        idle = b not in ("LONG SCALP", "SHORT SCALP")
        if idle:
            seen_idle = True
        assert not (seen_idle and not idle), "actionable row sorted below idle row"


# ---------------------------------------------------------------------------
# Phase 1 — numbers that agree with the chart
# ---------------------------------------------------------------------------

def _walk(n=300, seed=11, start=100.0):
    import random
    rng = random.Random(seed)
    out, p = [], start
    for _ in range(n):
        p *= 1 + rng.gauss(0.0004, 0.012)
        out.append(p)
    return out


def test_wilder_rsi_matches_reference_rma():
    """Wilder's RSI = RMA(gain)/RMA(loss). Reference: pandas ewm with
    alpha = 1/14, adjust=False, which is what TradingView's ta.rsi does."""
    import pandas as pd
    from scanner.data import _rsi

    closes = _walk()
    s = pd.Series(closes)
    d = s.diff().dropna()
    gain = d.clip(lower=0.0)
    loss = (-d).clip(lower=0.0)
    rma_g = gain.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
    rma_l = loss.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
    ref = 100 - 100 / (1 + rma_g / rma_l)
    assert _rsi(closes, 14) == pytest.approx(ref, abs=0.3)


def test_rsi_is_not_cutler_anymore():
    """The old 14-bar simple average differs from Wilder by several points
    on the same series — make sure we are no longer computing it."""
    from scanner.data import _rsi

    closes = _walk(seed=5)
    g = l = 0.0
    for i in range(1, 15):
        diff = closes[-i] - closes[-i - 1]
        g += max(diff, 0); l += max(-diff, 0)
    cutler = 100 - 100 / (1 + (g / 14) / (l / 14))
    assert abs(_rsi(closes, 14) - cutler) > 0.5


def test_rsi_flat_series_is_neutral():
    from scanner.data import _rsi
    assert _rsi([100.0] * 60, 14) == 50.0


def test_bollinger_uses_population_std():
    import statistics
    from scanner.data import signal_stats

    closes = _walk(n=80, seed=3)
    _, _, lower, upper = signal_stats(closes, closes[-1])
    last20 = closes[-20:]
    mid = statistics.fmean(last20)
    sd = statistics.pstdev(last20)          # population, like TradingView
    assert lower == pytest.approx(mid - 2 * sd, rel=1e-9)
    assert upper == pytest.approx(mid + 2 * sd, rel=1e-9)
    assert abs(sd - statistics.stdev(last20)) > 1e-9   # would differ if sample


def test_parallel_scan_matches_sequential():
    from scanner.scan import score_csp

    universe = DEFAULT_UNIVERSE[:16]
    tags = {s.ticker: s.tags for s in universe}
    seq = run_scan(SyntheticProvider(), universe,
                   ScanConfig(min_annualized_pct=0.0, max_workers=1))
    par = run_scan(SyntheticProvider(), universe,
                   ScanConfig(min_annualized_pct=0.0, max_workers=8))

    def key(c):
        return (c.ticker, c.expiry, c.strike)
    assert [key(c) for c in seq.csps] == [key(c) for c in par.csps]
    assert list(seq.infos) == list(par.infos)          # universe order kept
    assert ([score_csp(c, tags[c.ticker], ScanConfig()) for c in seq.csps]
            == [score_csp(c, tags[c.ticker], ScanConfig()) for c in par.csps])
    assert not seq.errors and not par.errors


def test_progress_callback_fires_once_per_symbol():
    seen = []
    universe = DEFAULT_UNIVERSE[:7]
    run_scan(SyntheticProvider(), universe, ScanConfig(max_workers=4),
             progress=lambda i, n, t: seen.append((i, n, t)))
    assert len(seen) == 7
    assert {t for _, _, t in seen} == {s.ticker for s in universe}
    assert sorted(i for i, _, _ in seen) == list(range(7))


def test_score_v2_rewards_ivr_and_expected_move_cushion():
    import dataclasses
    from scanner.scan import score_csp

    base = build_csps(_chain(), delta_range=(0.05, 0.6))[0]
    cfg = ScanConfig()
    plain = score_csp(base, frozenset(), cfg)          # no IVR, no EM: unchanged
    rich = dataclasses.replace(base, iv_rank=80.0)
    cheap = dataclasses.replace(base, iv_rank=10.0)
    assert score_csp(rich, frozenset(), cfg) > plain
    assert score_csp(cheap, frozenset(), cfg) < plain   # <20 IVR is penalized
    # strike a full expected move away beats one inside it
    em = (base.spot - base.strike) / 1.2                # cushion = 1.2 EM
    far = dataclasses.replace(base, expected_move=em)
    near = dataclasses.replace(base, expected_move=em * 3)   # cushion = 0.4 EM
    assert far.em_cushion == pytest.approx(1.2)
    assert score_csp(far, frozenset(), cfg) == pytest.approx(plain + 6.0)
    assert score_csp(near, frozenset(), cfg) == pytest.approx(plain)


def test_expected_move_and_dividend_yield():
    from scanner.data import UnderlyingInfo

    assert bs.expected_move(100.0, 0.30, 30) == pytest.approx(100 * 0.30 * (30 / 365) ** 0.5)
    assert bs.expected_move(100.0, 0.0, 30) == 0.0
    # a dividend lowers the forward: the put is worth more and its delta
    # is further from zero
    d0 = bs.put_delta(100, 90, 0.3, 45 / 365)
    dq = bs.put_delta(100, 90, 0.3, 45 / 365, q=0.04)
    assert abs(dq) > abs(d0)
    assert bs.put_price(100, 90, 0.3, 45 / 365, q=0.04) > bs.put_price(100, 90, 0.3, 45 / 365)
    # q=0 reproduces the classic formula exactly
    assert bs.put_price(100, 90, 0.3, 0.25, q=0.0) == bs.put_price(100, 90, 0.3, 0.25)
    info = UnderlyingInfo(ticker="X", spot=200.0, day_change_pct=0, pct_off_52w_high=0,
                          hist_vol_20d=0.25, rsi_14=50, iv_index=0.40)
    assert info.expected_move(30) == pytest.approx(bs.expected_move(200, 0.40, 30))
    info.iv_index = None                                 # falls back to realized vol
    assert info.expected_move(30) == pytest.approx(bs.expected_move(200, 0.25, 30))


def test_scan_carries_ivr_and_expected_move_onto_puts():
    universe = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL", "KO"})
    result = run_scan(SyntheticProvider(), universe, ScanConfig(min_annualized_pct=0.0))
    assert result.csps
    for c in result.csps:
        assert c.iv_rank is not None and 0 <= c.iv_rank <= 100
        assert c.expected_move and c.expected_move > 0
        assert c.em_cushion is not None and c.em_cushion > 0


# ---------------------------------------------------------------------------
# Phase 2 — track record, rulebook, book-aware picks
# ---------------------------------------------------------------------------

def test_track_record_roundtrip(tmp_path):
    from scanner import track

    universe = DEFAULT_UNIVERSE[:20]
    tags = {s.ticker: s.tags for s in universe}
    res = run_scan(SyntheticProvider(), universe, ScanConfig(min_annualized_pct=0.0))
    today = dt.date(2026, 9, 2)
    picks = track.picks_from_scan(res, tags, top_n=5, min_score=0.0, min_prob=0.0, today=today)
    assert 1 <= len(picks) <= 5
    assert len({p.ticker for p in picks}) == len(picks)          # one per ticker
    assert all(p.sector for p in picks) and all(p.iv > 0 for p in picks)

    path = tmp_path / "tr.jsonl"
    assert track.record(picks, path) == len(picks)
    assert track.record(picks, path) == 0                        # dedupe
    loaded = track.load(path)
    assert [p.key for p in loaded] == [p.key for p in picks]

    # nothing is due the day it is picked
    assert track.grade(loaded, SyntheticProvider(), today=today) == 0
    # 45 days on, every horizon inside the expiry (and expiry itself) is graded
    n = track.grade(loaded, SyntheticProvider(), today=today + dt.timedelta(days=45))
    assert n > 0
    for p in loaded:
        assert p.grades and "error" not in p.grades
        for g in p.grades.values():
            assert {"spot", "otm", "tested", "pct_of_max", "hit_50"} <= set(g)
            assert g["low_since"] is not None
    track.save(loaded, path)
    sc = track.scorecard(track.load(path))
    assert sc["picks"] == len(picks) and sc["graded"] == len(picks)
    assert sc["by_horizon"]["7"]["n"] >= 1
    assert sc["by_horizon"]["7"]["otm_pct"] is not None
    assert sc["by_sector"]


def test_track_grade_math():
    from scanner import track

    p = track.Pick(picked_on="2026-09-01", ticker="X", strategy="short put",
                   strike=90.0, expiry="2026-10-16", dte=45, spot=100.0,
                   mid=2.0, iv=0.30, delta=-0.2)
    up = track.grade_one(p, "7", spot_now=105.0, low_since=99.0, on=dt.date(2026, 9, 8))
    assert up["otm"] and not up["tested"] and up["pct_of_max"] > 0
    down = track.grade_one(p, "7", spot_now=85.0, low_since=84.0, on=dt.date(2026, 9, 8))
    assert not down["otm"] and down["tested"] and down["pct_of_max"] < 0
    at_exp = track.grade_one(p, "expiry", spot_now=95.0, low_since=91.0, on=dt.date(2026, 10, 16))
    assert at_exp["pct_of_max"] == 100.0 and at_exp["hit_50"]       # expired worthless


def test_picks_from_brief_parses_strike_zones():
    from scanner import track

    brief = {"candidates": [
        {"ticker": "TJX", "spot": "133.27", "rsi": "21.1", "zone": "Sell 125P", "signals": "a · b"},
        {"ticker": "ODFL", "spot": "186.72", "rsi": "26.9", "zone": "Sell 172-177P"},
        {"ticker": "CMI", "spot": "551.15", "rsi": "26.1", "zone": "515P / 495P spread"},
        {"ticker": "ZZZ", "spot": "10", "zone": "watch only"},                # no strike → skipped
    ]}
    picks = track.picks_from_brief(brief, today=dt.date(2026, 9, 2))
    got = {p.ticker: p.strike for p in picks}
    assert got == {"TJX": 125.0, "ODFL": 174.5, "CMI": 505.0}
    assert picks[0].signals == ["a", "b"] and picks[0].source == "brief"
    assert picks[0].expiry == "2026-10-17"


def _rows():
    return [
        {"symbol": "SNDK  261016P01220000", "underlying": "SNDK", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 30.0, "dte": 44, "expires": "10/16/2026"},
        {"symbol": "SNDK  261016C01940000", "underlying": "SNDK", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 40.0, "dte": 44, "expires": "10/16/2026"},   # same position
        {"symbol": "MU    261016P00750000", "underlying": "MU", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 12.0, "dte": 44, "expires": "10/16/2026"},
        {"symbol": "MU    270115P00800000", "underlying": "MU", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 60.0, "dte": 500, "expires": "01/15/2027"},  # LEAP: excluded
        {"symbol": "KO", "underlying": "KO", "type": "Equity", "direction": "LONG", "qty": 200,
         "mark": 70.0, "dte": None, "expires": None},                                         # stock: excluded
        {"symbol": "./NGX6 LNEX6 261027P2.5", "underlying": "/NGX6", "type": "Future Option",
         "direction": "SHORT", "qty": 2, "mark": 0.04, "dte": 55, "expires": "10/27/2026"},
        {"symbol": "XLU   261016P00080000", "underlying": "XLU", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 1.0, "dte": 44, "expires": "10/16/2026"},
        {"symbol": "SO    261016P00085000", "underlying": "SO", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 1.5, "dte": 44, "expires": "10/16/2026"},
        {"symbol": "NEE   261016P00070000", "underlying": "NEE", "type": "Equity Option",
         "direction": "SHORT", "qty": 1, "mark": 1.2, "dte": 44, "expires": "10/16/2026"},
    ]


def test_rulebook_counts_positions_the_traders_way():
    from scanner import rules

    tags = {s.ticker: s.tags for s in DEFAULT_UNIVERSE}
    rows = _rows()
    assert len(rules.position_groups(rows)) == 6      # SNDK strangle=1, MU(non-LEAP)=1, /NG, XLU, SO, NEE
    assert rules.per_ticker(rows)["SNDK"] == 1 and rules.per_ticker(rows)["MU"] == 1
    sectors = rules.per_sector(rows, tags)
    # SNDK is not in the universe -> other; the /NGX6 leg resolves to its /NG root
    assert sectors["utilities"] == 3 and sectors["semis"] == 1
    assert sectors["other"] == 1 and sectors["futures-energy"] == 1
    assert rules.futures_root("/NGX6") == "/NG" and rules.futures_root("/ESZ26") == "/ES"
    assert rules.futures_root("AAPL") == "AAPL"
    assert rules.futures_margin(rows) == pytest.approx(2 * 3_800)   # /NG estimate × 2 contracts

    checks = {c.name: c for c in rules.check(rows, tags, balances={"net_liq": 450_000, "bp_used": 120_000, "futures_margin": 7_600})}
    assert checks["Open positions"].value == 6 and checks["Open positions"].status == "ok"
    assert checks["Per sector"].status == "breach" and "utilities" in checks["Per sector"].detail
    assert checks["Buying power used"].value == pytest.approx(26.7, abs=0.1)
    assert checks["Buying power used"].status == "ok"
    assert checks["Futures sleeve"].value == 7_600 and checks["Futures sleeve"].status == "ok"
    assert checks["β-delta (SPY)"].status == "n/a"
    assert rules.worst_status(list(checks.values())) == "breach"

    hot = rules.check(rows, tags, balances={"net_liq": 100_000, "bp_used": 45_000}, beta_delta=180.0)
    by = {c.name: c.status for c in hot}
    assert by["Buying power used"] == "breach" and by["β-delta (SPY)"] == "breach"
    assert rules.parse_option("AAPL  261016P00295000") == {"root": "AAPL", "strike": 295.0, "is_put": True, "futures": False}
    assert rules.parse_option("./NGX6 LNEX6 261027P2.5")["root"] == "/NG"


def test_beta_weighted_delta_signs_and_scaling():
    from scanner import rules

    rows = [
        {"symbol": "AAPL  261016P00295000", "underlying": "AAPL", "type": "Equity Option",
         "direction": "SHORT", "qty": 2, "mark": 4.0, "dte": 44},
        {"symbol": "KO", "underlying": "KO", "type": "Equity", "direction": "LONG", "qty": 100, "mark": 70.0, "dte": None},
    ]
    spot = {"AAPL": 310.0, "KO": 70.0}
    beta = {"AAPL": 1.2, "KO": 0.5}
    total, by = rules.beta_weighted_delta(rows, spot.get, beta.get, spy_spot=650.0)
    assert total is not None and by["AAPL"] > 0 and by["KO"] > 0     # short put and long stock are both long delta
    # KO: 100 sh × β0.5 × (70/650) = 5.38 SPY-deltas
    assert by["KO"] == pytest.approx(100 * 0.5 * 70 / 650, abs=0.1)
    assert total == pytest.approx(by["AAPL"] + by["KO"], abs=0.2)
    none_total, _ = rules.beta_weighted_delta(rows, lambda u: None, beta.get, spy_spot=650.0)
    assert none_total is None


def test_candidate_fit_and_labels():
    import numpy as np
    import pandas as pd
    from scanner import correlation as corr

    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 60)
    closes = pd.DataFrame({
        "A": 100 * np.exp(np.cumsum(base * 0.01)),
        "B": 100 * np.exp(np.cumsum((base + rng.normal(0, 0.3, 60)) * 0.01)),   # tracks A
        "C": 100 * np.exp(np.cumsum(rng.normal(0, 1, 60) * 0.01)),             # independent
    })
    fit = corr.candidate_fit(["B", "C", "ZZ"], ["A"], closes=closes)
    assert fit["B"] > 0.7 and abs(fit["C"]) < 0.4 and fit["ZZ"] is None
    assert corr.fit_label(fit["B"]).startswith("⚠️")
    assert "adds diversification" in corr.fit_label(0.1)
    assert corr.fit_label(None) == "no book data"
    assert corr.candidate_fit(["B"], []) == {"B": None}


def test_track_due_and_grade_with_quotes(tmp_path):
    import json
    from scanner import track

    p1 = track.Pick(picked_on="2026-09-01", ticker="TJX", strategy="short put", strike=125.0,
                    expiry="2026-10-16", dte=45, spot=133.0, mid=3.0, iv=0.35)
    p2 = track.Pick(picked_on="2026-09-01", ticker="SO", strategy="short put", strike=85.0,
                    expiry="2026-10-16", dte=45, spot=88.0, mid=1.5, iv=0.22)
    today = dt.date(2026, 9, 16)                     # 15 days on: 7 and 14 due, 30 not
    d = track.due([p1, p2], today)
    assert set(d) == {"TJX", "SO"} and d["TJX"]["labels"] == ["14", "7"]
    quotes = {"TJX": {"spot": 138.0, "low_since": 130.5}}          # no SO quote yet
    n = track.grade_with_quotes([p1, p2], quotes, today)
    assert n == 2 and set(p1.grades) == {"7", "14"} and not p2.grades
    assert p1.grades["14"]["otm"] and not p1.grades["14"]["tested"]
    assert p1.grades["14"]["pct_of_max"] > 0
    assert track.due([p1, p2], today) == {"SO": {"since": "2026-09-01", "labels": ["14", "7"]}}

    # CLI: record from brief -> due -> grade --quotes -> show
    path = tmp_path / "t.jsonl"
    track.save([p1, p2], path)
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"SO": {"spot": 86.0, "low_since": 84.9}}))
    assert track.main(["grade", "--quotes", str(q), "--today", "2026-09-16", "--path", str(path)]) == 0
    reloaded = {p.ticker: p for p in track.load(path)}
    assert reloaded["SO"].grades and reloaded["SO"].grades["7"]["tested"]   # low 84.9 < 85 strike
    assert set(reloaded["SO"].grades) == {"7", "14"}
    assert track.main(["due", "--today", "2026-09-16", "--path", str(path)]) == 0


# ---------------------------------------------------------------------------
# Phase 3 — roll assistant, alerts, plain-English layer
# ---------------------------------------------------------------------------

def test_roll_candidates_price_both_repairs():
    from scanner import roll

    prov = SyntheticProvider()
    info = prov.underlying("AAPL")
    cur = info.expiries[0]
    chain = prov.chain("AAPL", cur)
    short = [q for q in chain.puts if q.strike < chain.spot][-3]     # a near-the-money put we're "short"
    mark = short.mid
    rolls = roll.roll_candidates(prov, "AAPL", short.strike, True, cur,
                                 current_mark=mark, original_credit=mark * 0.6)
    assert rolls, "expected roll candidates from later expiries"
    assert {r.label for r in rolls} <= {"same strike", "one strike out"}
    assert all(r.expiry > cur and r.dte > chain.dte for r in rolls)
    same = [r for r in rolls if r.label == "same strike"]
    assert same and all(r.strike == short.strike for r in same)
    out = [r for r in rolls if r.label == "one strike out"]
    assert out and all(r.strike < short.strike for r in out)
    # further-dated same strike is worth more than the near one → a credit
    assert any(r.is_credit for r in same)
    for r in rolls:
        assert r.net == pytest.approx(r.new_mid - mark, abs=0.011)
        assert r.net_dollars == pytest.approx(r.net * r.multiplier)
        assert -1.0 <= r.delta <= 0.0
    # sorted credits first, biggest first
    nets = [r.net for r in rolls if r.is_credit]
    assert nets == sorted(nets, reverse=True)
    best = roll.best_roll(rolls)
    assert best is not None and best.is_credit and best.net == nets[0]
    assert roll.best_roll([]) is None


def test_alerts_levels_and_text():
    from scanner import alerts, rules

    universe = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL", "KO", "PLTR"})
    tags = {s.ticker: s.tags for s in universe}
    res = run_scan(SyntheticProvider(), universe, ScanConfig(min_annualized_pct=0.0))
    # force one quality name into a washout and one held name into earnings week
    res.infos["KO"].rsi_14 = 24.0
    res.infos["AAPL"].next_earnings = dt.date(2026, 9, 5)
    res.infos["PLTR"].rsi_14 = 20.0                     # not blue-chip/etf → no watch alert
    positions = [
        {"underlying": "AAPL", "display": "AAPL 10/16/26 $295 PUT", "suggestion": "💰 CLOSE — 55% captured, hit the 50% rule"},
        {"underlying": "MU", "display": "MU 10/16/26 $750 PUT", "suggestion": "⏰ 19 DTE — inside the 21-DTE roll/close window"},
        {"underlying": "SNDK", "display": "SNDK 10/16/26 $1220 PUT", "suggestion": "hold"},
    ]
    checks = [rules.RuleCheck("Per sector", 3, 2, "breach", "over: utilities (3)"),
              rules.RuleCheck("Open positions", 18, 20, "warn", "18 of 20")]
    out = alerts.build_alerts(res, tags, positions, checks, today=dt.date(2026, 9, 2))
    levels = [(a.level, a.ticker) for a in out]
    assert ("act", "AAPL") in levels                    # close signal
    assert ("watch", "MU") in levels                    # DTE window
    assert ("act", "") in levels and ("watch", "") in levels   # rule breach + warn
    assert any(a.level == "watch" and a.ticker == "KO" and "RSI 24" in a.text for a in out)
    assert any(a.level == "act" and a.ticker == "AAPL" and "reports" in a.text for a in out)
    assert not any(a.ticker == "PLTR" for a in out)
    assert not any("SNDK" in a.text for a in out)
    assert [a.level for a in out] == sorted((a.level for a in out), key=lambda l: alerts.LEVEL_ORDER[l])
    txt = alerts.format_text(out, "09/02")
    assert txt.startswith("Scanner alerts 09/02") and "ACT TODAY" in txt and "WATCH" in txt
    assert alerts.format_text([]) == "Nothing needs action."
    assert not alerts.smtp_configured()
    assert "not configured" in alerts.send_email(out)


def test_presentation_layer():
    from scanner import present
    from scanner.scan import score_csp

    c = build_csps(_chain(), entry_signals=frozenset({"RSI<=30", "LowerBB"}), iv_rank=42.0,
                   expected_move=8.0)[0]
    c.rsi_14 = 27.0
    v = present.verdict(c)
    assert v.startswith(f"Sell the TEST {c.strike:g} put") and "collect $" in v and "cash" in v
    ch = present.chips(c)
    assert ch[0].startswith("🟢 RSI 27") and "🟢 band" in ch and "⚪ 50-SMA" in ch
    assert any(x.startswith("🟢 IVR 42") for x in ch)
    assert any("EM" in x for x in ch)
    assert "RSI<=30" in present.why(c) and "IVR 42" in present.why(c)
    assert "at the low of day" in present.why(c, at_day_low=True)

    for name in present.PRESETS:
        p = present.preset(name)
        assert set(p) >= {"timeframe", "tags", "dte", "delta", "min_annual", "min_oi"}
        assert p["dte"][0] <= p["dte"][1] and p["delta"][0] < p["delta"][1]
    assert present.preset("Scalp · intraday")["timeframe"] == "5m"
    assert present.preset("Custom") == present.DEFAULTS

    universe = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL", "KO", "/ES"})
    tags = {s.ticker: s.tags for s in universe}
    res = run_scan(SyntheticProvider(), universe, ScanConfig(min_annualized_pct=0.0))
    picks = []
    seen = set()
    for x in res.csps:
        if x.ticker not in seen:
            seen.add(x.ticker); picks.append((score_csp(x, tags[x.ticker], ScanConfig()), x))
    brief = present.brief_from_result(res, tags, picks[:3], when=dt.datetime(2026, 9, 2, 8, 46))
    assert brief["title"] and brief["date"].endswith("09/02/2026") and brief["pulled"] == "8:46am ET"
    assert len(brief["candidates"]) == 3 and all(k in brief["candidates"][0] for k in ("ticker", "spot", "rsi", "zone", "signals"))
    assert brief["posture"]["rows"][0]["sym"] == "/ES"
    assert "footer" in brief


def test_news_parse_score_and_split():
    import datetime as _d
    from scanner import news

    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Fed holds rates steady, Powell flags tariff risk to inflation</title>
        <link>https://x/1</link><pubDate>Wed, 02 Sep 2026 14:05:00 GMT</pubDate></item>
      <item><title>Apple unveils new iPhone; shares slip</title>
        <link>https://x/2</link><pubDate>Wed, 02 Sep 2026 13:00:00 GMT</pubDate></item>
      <item><title>Fed holds rates steady, Powell flags tariff risk to inflation</title>
        <link>https://x/dup</link><pubDate>Wed, 02 Sep 2026 14:00:00 GMT</pubDate></item>
      <item><title>Local bakery wins award</title><link>https://x/3</link>
        <pubDate>Tue, 01 Sep 2026 09:00:00 GMT</pubDate></item>
      <item><title>TJX falls for a fifth day as off-price retail sells off - Reuters</title>
        <link>https://x/4</link><source url="https://reuters.com">Reuters</source>
        <pubDate>Wed, 02 Sep 2026 14:50:00 GMT</pubDate></item>
    </channel></rss>"""
    atom = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Crude jumps 4% as OPEC surprises with cut</title>
        <link href="https://x/5"/><published>2026-09-02T14:30:00Z</published></entry></feed>"""
    items = news.parse(rss, "CNBC") + news.parse(atom, "Fed")
    assert len(items) == 6
    tjx = next(i for i in items if i.title.startswith("TJX"))
    assert tjx.source == "Reuters" and " - Reuters" not in tjx.title
    assert items[0].published == _d.datetime(2026, 9, 2, 14, 5, tzinfo=_d.timezone.utc)

    now = _d.datetime(2026, 9, 2, 15, 0, tzinfo=_d.timezone.utc)
    ranked = news.rank(items, watch=["TJX", "/CL"], now=now)
    assert len(ranked) == 5                          # duplicate Fed headline dropped
    by = {i.title[:5]: i for i in ranked}
    assert by["Fed h"].level == "move" and "fomc" not in by["Fed h"].tags and "tariff" in by["Fed h"].tags
    assert "TJX" in by["TJX f"].tickers and "your name" in by["TJX f"].tags and by["TJX f"].score >= 6
    assert "/CL" in by["Crude"].tickers and by["Crude"].level == "move"
    assert "AAPL" in by["Apple"].tickers and by["Apple"].level != "move"
    assert by["Local"].level == "info" and by["Local"].tickers == []
    assert ranked[0].score >= ranked[-1].score
    assert by["TJX f"].age(now) == "10m" and by["Local"].age(now) == "30h"

    buckets = news.split(ranked, watch=["TJX", "/CL"])
    assert set(buckets) == {"move", "mine", "rest"}
    assert by["Local"] in buckets["rest"] and by["Apple"] in buckets["rest"]
    assert all(i.level == "move" for i in buckets["move"])
    assert sum(len(v) for v in buckets.values()) == len(ranked)

    # stoplist: uppercase words that are not tickers, unless written as $XYZ
    assert news.tag_tickers("AI stocks rally as CEO of IT firm resigns") == []
    assert news.tag_tickers("$SO breaks out") == ["SO"]
    assert "HD" in news.tag_tickers("Home Depot beats on earnings")
    assert "NVDA" in news.tag_tickers("NVDA slides 3%")
    assert "TJX" in news.ticker_feed("TJX") and "Treasury" in news.ticker_feed("/ZN")
