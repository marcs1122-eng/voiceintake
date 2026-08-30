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


def test_universe_filters():
    etfs = filter_universe(DEFAULT_UNIVERSE, include_tags={"etf"})
    assert etfs and all(s.has("etf") for s in etfs)
    no_etfs = filter_universe(DEFAULT_UNIVERSE, exclude_tags={"etf"})
    assert no_etfs and not any(s.has("etf") for s in no_etfs)
    picks = filter_universe(DEFAULT_UNIVERSE, tickers={"SPY", "AAPL"})
    assert {s.ticker for s in picks} == {"SPY", "AAPL"}
