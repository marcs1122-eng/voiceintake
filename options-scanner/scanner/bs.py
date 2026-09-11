"""Black-Scholes helpers.

Chains give per-contract implied vol but no greeks, so delta and
probability estimates are computed here. Probabilities are risk-neutral
lognormal estimates — good ranking signals, not gospel.

`q` is the underlying's continuous dividend yield (0.03 = 3%). Ignoring it
overstates put value on high-yield names (KO, MO, VZ, XLU), which in turn
solves to an IV that is too high. Every function defaults q to 0 so callers
that don't know the yield get the classic no-dividend formula.
"""

import math

SQRT_2 = math.sqrt(2.0)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT_2))


def _d1_d2(spot: float, strike: float, iv: float, t_years: float, r: float,
           q: float = 0.0) -> tuple[float, float]:
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 0:
        raise ValueError("spot, strike, iv, and time must be positive")
    vol_sqrt_t = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * t_years) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def put_delta(spot: float, strike: float, iv: float, t_years: float,
              r: float = 0.04, q: float = 0.0) -> float:
    """Black-Scholes put delta (negative, in [-1, 0])."""
    d1, _ = _d1_d2(spot, strike, iv, t_years, r, q)
    return math.exp(-q * t_years) * (_norm_cdf(d1) - 1.0)


def call_delta(spot: float, strike: float, iv: float, t_years: float,
               r: float = 0.04, q: float = 0.0) -> float:
    d1, _ = _d1_d2(spot, strike, iv, t_years, r, q)
    return math.exp(-q * t_years) * _norm_cdf(d1)


def prob_below(spot: float, level: float, iv: float, t_years: float,
               r: float = 0.04, q: float = 0.0) -> float:
    """Risk-neutral probability the underlying finishes below `level` at expiry."""
    _, d2 = _d1_d2(spot, level, iv, t_years, r, q)
    return _norm_cdf(-d2)


def prob_above(spot: float, level: float, iv: float, t_years: float,
               r: float = 0.04, q: float = 0.0) -> float:
    return 1.0 - prob_below(spot, level, iv, t_years, r, q)


def put_price(spot: float, strike: float, iv: float, t_years: float,
              r: float = 0.04, q: float = 0.0) -> float:
    d1, d2 = _d1_d2(spot, strike, iv, t_years, r, q)
    return (strike * math.exp(-r * t_years) * _norm_cdf(-d2)
            - spot * math.exp(-q * t_years) * _norm_cdf(-d1))


def call_price(spot: float, strike: float, iv: float, t_years: float,
               r: float = 0.04, q: float = 0.0) -> float:
    d1, d2 = _d1_d2(spot, strike, iv, t_years, r, q)
    return (spot * math.exp(-q * t_years) * _norm_cdf(d1)
            - strike * math.exp(-r * t_years) * _norm_cdf(d2))


def expected_move(spot: float, iv: float, dte: int) -> float:
    """One-standard-deviation move to expiry, in price units. This is what
    "outside one expected move" means when picking a strike."""
    if spot <= 0 or iv <= 0 or dte <= 0:
        return 0.0
    return spot * iv * math.sqrt(dte / 365.0)


def implied_vol(price: float, spot: float, strike: float, t_years: float,
                r: float = 0.04, is_put: bool = True, q: float = 0.0) -> float:
    """Back out IV from an option price by bisection. Returns 0.0 when the
    price is outside the no-arbitrage band (stale/crossed quote)."""
    if price <= 0 or spot <= 0 or strike <= 0 or t_years <= 0:
        return 0.0
    intrinsic = max(strike - spot, 0.0) if is_put else max(spot - strike, 0.0)
    if price <= intrinsic * 0.999:
        return 0.0
    pricer = put_price if is_put else call_price
    lo, hi = 0.005, 5.0
    if price >= pricer(spot, strike, hi, t_years, r, q):
        return 0.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if pricer(spot, strike, mid, t_years, r, q) < price:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2.0, 4)
