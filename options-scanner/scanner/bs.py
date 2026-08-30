"""Black-Scholes helpers.

Yahoo chains give per-contract implied vol but no greeks, so delta and
probability estimates are computed here. Probabilities are risk-neutral
lognormal estimates — good ranking signals, not gospel.
"""

import math

SQRT_2 = math.sqrt(2.0)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT_2))


def _d1_d2(spot: float, strike: float, iv: float, t_years: float, r: float) -> tuple[float, float]:
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 0:
        raise ValueError("spot, strike, iv, and time must be positive")
    vol_sqrt_t = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def put_delta(spot: float, strike: float, iv: float, t_years: float, r: float = 0.04) -> float:
    """Black-Scholes put delta (negative, in [-1, 0])."""
    d1, _ = _d1_d2(spot, strike, iv, t_years, r)
    return _norm_cdf(d1) - 1.0


def call_delta(spot: float, strike: float, iv: float, t_years: float, r: float = 0.04) -> float:
    d1, _ = _d1_d2(spot, strike, iv, t_years, r)
    return _norm_cdf(d1)


def prob_below(spot: float, level: float, iv: float, t_years: float, r: float = 0.04) -> float:
    """Risk-neutral probability the underlying finishes below `level` at expiry."""
    _, d2 = _d1_d2(spot, level, iv, t_years, r)
    return _norm_cdf(-d2)


def prob_above(spot: float, level: float, iv: float, t_years: float, r: float = 0.04) -> float:
    return 1.0 - prob_below(spot, level, iv, t_years, r)


def put_price(spot: float, strike: float, iv: float, t_years: float, r: float = 0.04) -> float:
    d1, d2 = _d1_d2(spot, strike, iv, t_years, r)
    return strike * math.exp(-r * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def call_price(spot: float, strike: float, iv: float, t_years: float, r: float = 0.04) -> float:
    d1, d2 = _d1_d2(spot, strike, iv, t_years, r)
    return spot * _norm_cdf(d1) - strike * math.exp(-r * t_years) * _norm_cdf(d2)
