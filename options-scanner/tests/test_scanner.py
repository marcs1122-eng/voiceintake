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


def test_universe_filters():
    etfs = filter_universe(DEFAULT_UNIVERSE, include_tags={"etf"})
    assert etfs and all(s.has("etf") for s in etfs)
    no_etfs = filter_universe(DEFAULT_UNIVERSE, exclude_tags={"etf"})
    assert no_etfs and not any(s.has("etf") for s in no_etfs)
    picks = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL"})
    assert {s.ticker for s in picks} == {"SPY", "AAPL"}
