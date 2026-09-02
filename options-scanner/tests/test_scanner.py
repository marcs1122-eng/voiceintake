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
