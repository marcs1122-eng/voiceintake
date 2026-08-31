"""tastytrade data provider: real-time option chains for stocks, ETFs, AND
futures, plus your live account positions.

Setup (one time):
  1. Log into tastytrade, go to https://developer.tastytrade.com and create
     an OAuth application + grant to get a client secret and refresh token.
  2. Put them in options-scanner/.env (never commit this file):
         TASTYTRADE_CLIENT_SECRET=...
         TASTYTRADE_REFRESH_TOKEN=...
  3. Validate: python -m scanner.tastytrade_check

Design notes:
  - Quotes (bid/ask/mark/open interest) come from tastytrade's synchronous
    market-data REST endpoint, batched per expiry — no websocket needed.
  - tastytrade's REST quotes don't include greeks, so IV is backed out of
    the mid price with the Black-Scholes solver in bs.py and delta follows
    from that, same as the Yahoo path.
  - Price history for RSI/SMA/Bollinger still comes from Yahoo (tastytrade
    serves candles only over its streamer); futures roots map to Yahoo
    continuous contracts.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os

from . import bs
from .data import ChainSnapshot, DataProvider, OptionQuote, UnderlyingInfo, YFinanceProvider
from .futures import is_futures, product_for

QUOTE_BATCH = 90          # market-data endpoint symbol limit per call
MAX_STRIKES_EACH_SIDE = 40  # strikes fetched around the money per expiry

_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    """tastytrade SDK v13+ is async-only. Run its coroutines on one
    persistent event loop so SDK connection state survives across calls
    (asyncio.run would tear the loop down every time)."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)


def _load_env_file() -> None:
    """Minimal .env loader so the scanner has no python-dotenv dependency."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def has_credentials() -> bool:
    _load_env_file()
    return bool(os.environ.get("TASTYTRADE_CLIENT_SECRET")
                and os.environ.get("TASTYTRADE_REFRESH_TOKEN"))


class TastytradeProvider(DataProvider):
    def __init__(self, session=None, timeframe: str = "1d"):
        from tastytrade import Session
        self.timeframe = timeframe
        if session is None:
            _load_env_file()
            secret = os.environ.get("TASTYTRADE_CLIENT_SECRET")
            token = os.environ.get("TASTYTRADE_REFRESH_TOKEN")
            if not (secret and token):
                raise RuntimeError(
                    "Set TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN "
                    "in options-scanner/.env (see scanner/tastytrade_provider.py)")
            session = Session(provider_secret=secret, refresh_token=token)
        self.session = session
        self._yf = None                       # lazy Yahoo helper for history
        self._equity_chains: dict[str, dict] = {}
        self._future_chains: dict[str, dict] = {}
        self._info_cache: dict[str, UnderlyingInfo] = {}

    # ------------------------------------------------------------------
    # Underlying info: history/technicals from Yahoo, live spot from tasty
    # ------------------------------------------------------------------

    def _yahoo(self) -> YFinanceProvider:
        if self._yf is None:
            self._yf = YFinanceProvider(timeframe=self.timeframe)
        return self._yf

    def underlying(self, ticker: str) -> UnderlyingInfo:
        if ticker in self._info_cache:
            return self._info_cache[ticker]
        try:
            info = self._yahoo().underlying(ticker)
        except Exception:
            info = UnderlyingInfo(ticker=ticker, spot=0.0, day_change_pct=0.0,
                                  pct_off_52w_high=0.0, hist_vol_20d=0.0,
                                  rsi_14=50.0)
        # Intraday scalp mode: replace Yahoo's ~15-min-delayed candle signals
        # with LIVE candles from tastytrade's dxFeed streamer when possible.
        if self.timeframe != "1d":
            closes = self._candle_closes(ticker)
            if len(closes) >= 21:
                from .data import signal_stats
                (info.rsi_14, info.sma_50,
                 info.boll_lower, info.boll_upper) = signal_stats(closes, info.spot or closes[-1])

        md = self._live_quote(ticker)
        if md is not None:
            if md.mark or md.last:
                info.spot = float(md.mark or md.last)
            # today's session extremes, live from tastytrade (like the tasty watchlist)
            hi = md.day_high_price or md.day_high
            lo = md.day_low_price or md.day_low
            if hi:
                info.day_high = float(hi)
            if lo:
                info.day_low = float(lo)
        info.expiries = self._expiries(ticker)
        self._info_cache[ticker] = info
        return info

    # Bars of history to backfill per timeframe (enough for a 50-bar SMA).
    _CANDLE_LOOKBACK = {"5m": dt.timedelta(days=3), "10m": dt.timedelta(days=5),
                        "1h": dt.timedelta(days=14), "4h": dt.timedelta(days=45)}

    def _streamer_symbol(self, ticker: str) -> str | None:
        """dxFeed symbol for candles: the ticker for equities, the front
        contract's streamer symbol for futures roots."""
        if not is_futures(ticker):
            return ticker
        try:
            from tastytrade.instruments import Future
            front = self._front_future_symbol(ticker)
            if not front:
                return None
            fut = _run(Future.get(self.session, [front]))
            fut = fut[0] if isinstance(fut, list) else fut
            return fut.streamer_symbol
        except Exception:
            return None

    def _candle_closes(self, ticker: str) -> list[float]:
        """Live candle closes from the dxFeed streamer, oldest first. Returns
        [] on any failure so callers fall back to Yahoo's delayed bars."""
        symbol = self._streamer_symbol(ticker)
        if not symbol:
            return []
        lookback = self._CANDLE_LOOKBACK.get(self.timeframe)
        if lookback is None:
            return []

        async def fetch() -> list[float]:
            from tastytrade import DXLinkStreamer
            from tastytrade.dxfeed import Candle
            start = dt.datetime.now(dt.timezone.utc) - lookback
            bars: dict[int, float] = {}
            async with DXLinkStreamer(self.session) as streamer:
                await streamer.subscribe_candle([symbol], interval=self.timeframe,
                                                start_time=start)
                deadline = asyncio.get_event_loop().time() + 8.0
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        c = await asyncio.wait_for(streamer.get_event(Candle), timeout=1.5)
                    except asyncio.TimeoutError:
                        if len(bars) >= 21:   # history flushed; quiet means done
                            break
                        continue
                    if c.close is not None and c.time is not None:
                        bars[int(c.time)] = float(c.close)
            return [close for _, close in sorted(bars.items())]

        try:
            return _run(fetch())
        except Exception:
            return []

    def _live_quote(self, ticker: str):
        from tastytrade.market_data import get_market_data_by_type
        try:
            if is_futures(ticker):
                front = self._front_future_symbol(ticker)
                md = _run(get_market_data_by_type(self.session, futures=[front])) if front else []
            else:
                md = _run(get_market_data_by_type(self.session, equities=[ticker]))
            return md[0] if md else None
        except Exception:
            return None

    def _live_spot(self, ticker: str) -> float | None:
        md = self._live_quote(ticker)
        if md is not None and (md.mark or md.last):
            return float(md.mark or md.last)
        return None

    # ------------------------------------------------------------------
    # Chains
    # ------------------------------------------------------------------

    def _equity_chain(self, ticker: str) -> dict:
        """{expiry_date: NestedOptionChainExpiration} plus shares/contract."""
        if ticker not in self._equity_chains:
            from tastytrade.instruments import NestedOptionChain
            chains = _run(NestedOptionChain.get(self.session, ticker))
            if not chains:
                raise ValueError(f"no option chain for {ticker}")
            chain = chains[0]
            self._equity_chains[ticker] = {
                "multiplier": float(chain.shares_per_contract or 100),
                "expirations": {e.expiration_date: e for e in chain.expirations},
            }
        return self._equity_chains[ticker]

    def _future_chain(self, ticker: str) -> dict:
        """{expiry_date: (underlying_future_symbol, NestedFutureOptionChainExpiration)}."""
        if ticker not in self._future_chains:
            from tastytrade.instruments import NestedFutureOptionChain
            chain = _run(NestedFutureOptionChain.get(self.session, ticker))
            expirations: dict[dt.date, tuple[str, object]] = {}
            for sub in chain.option_chains:
                for e in sub.expirations:
                    # keep the nearest-listed contract per expiry date
                    expirations.setdefault(e.expiration_date, (e.underlying_symbol, e))
            self._future_chains[ticker] = {"expirations": expirations}
        return self._future_chains[ticker]

    def _expiries(self, ticker: str) -> list[dt.date]:
        try:
            if is_futures(ticker):
                exps = self._future_chain(ticker)["expirations"]
            else:
                exps = self._equity_chain(ticker)["expirations"]
            return sorted(exps.keys())
        except Exception:
            return []

    def _front_future_symbol(self, ticker: str) -> str | None:
        try:
            exps = self._future_chain(ticker)["expirations"]
            if not exps:
                return None
            return exps[min(exps.keys())][0]
        except Exception:
            return None

    def chain(self, ticker: str, expiry: dt.date) -> ChainSnapshot:
        from tastytrade.market_data import get_market_data_by_type

        prod = product_for(ticker)
        if is_futures(ticker):
            _, exp = self._future_chain(ticker)["expirations"][expiry]
            multiplier = prod.multiplier if prod else 100.0
        else:
            exp = self._equity_chain(ticker)["expirations"][expiry]
            multiplier = self._equity_chain(ticker)["multiplier"]

        spot = self.underlying(ticker).spot
        strikes = sorted(exp.strikes, key=lambda s: float(s.strike_price))
        # trim far wings so each expiry stays within a couple of quote batches
        below = [s for s in strikes if float(s.strike_price) <= spot][-MAX_STRIKES_EACH_SIDE:]
        above = [s for s in strikes if float(s.strike_price) > spot][:MAX_STRIKES_EACH_SIDE]
        strikes = below + above

        symbols = [s.put for s in strikes] + [s.call for s in strikes]
        quotes: dict[str, object] = {}
        kwarg = "future_options" if is_futures(ticker) else "options"
        for i in range(0, len(symbols), QUOTE_BATCH):
            batch = symbols[i:i + QUOTE_BATCH]
            for md in _run(get_market_data_by_type(self.session, **{kwarg: batch})):
                quotes[md.symbol] = md

        t_years = max((expiry - dt.date.today()).days, 1) / 365.0
        puts, calls = [], []
        for s in strikes:
            k = float(s.strike_price)
            puts.append(self._quote(quotes.get(s.put), k, spot, t_years, True))
            calls.append(self._quote(quotes.get(s.call), k, spot, t_years, False))
        return ChainSnapshot(ticker, spot, expiry,
                             [q for q in puts if q], [q for q in calls if q],
                             multiplier=multiplier)

    @staticmethod
    def _quote(md, strike: float, spot: float, t_years: float,
               is_put: bool) -> OptionQuote | None:
        if md is None:
            return None
        bid = float(md.bid or 0)
        ask = float(md.ask or 0)
        mid = (bid + ask) / 2 if (bid or ask) else float(md.mark or 0)
        iv = bs.implied_vol(mid, spot, strike, t_years, is_put=is_put) if spot else 0.0
        return OptionQuote(strike=strike, bid=bid, ask=ask, iv=iv,
                           open_interest=int(md.open_interest or 0),
                           volume=int(md.volume or 0))


# ----------------------------------------------------------------------
# Account positions (read-only)
# ----------------------------------------------------------------------

import re as _re

_OCC_RE = _re.compile(r"^([A-Z0-9]+)\s+(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")
_FUT_RE = _re.compile(r"^(\.\/[A-Z0-9]+)\s+\S+\s+(\d{2})(\d{2})(\d{2})([CP])([\d.]+)$")


def pretty_symbol(raw: str) -> str:
    """Turn tastytrade option symbols into something readable:
    'NFLX  261120C00085000' -> 'NFLX 11/20/26 $85 CALL'
    './6EZ6 EUUV6 261009P1.15' -> '/6EZ6 10/09/26 $1.15 PUT'."""
    raw = (raw or "").strip()
    m = _OCC_RE.match(raw)
    if m:
        root, yy, mm, dd, cp, k = m.groups()
        strike = int(k) / 1000
        kind = "PUT" if cp == "P" else "CALL"
        return f"{root} {mm}/{dd}/{yy} ${strike:g} {kind}"
    m = _FUT_RE.match(raw)
    if m:
        root, yy, mm, dd, cp, k = m.groups()
        kind = "PUT" if cp == "P" else "CALL"
        return f"{root.lstrip('.')} {mm}/{dd}/{yy} ${float(k):g} {kind}"
    return raw  # stock/unknown: leave as-is


def position_suggestion(pct_of_max: float | None, dte: int | None,
                        is_short: bool, days_held: int | None = None) -> str:
    """Plain-language management call for a short option, using Mac's ladder:
    take profit at 25% on day one, 30% on day two, then 50% of max (or the
    21-DTE roll/close window, whichever comes first). Defend when tested."""
    if not is_short or pct_of_max is None:
        return ""
    # Only call it TESTED when the mark is meaningfully above entry (15%+);
    # a few cents against you is noise, not a signal.
    if pct_of_max <= -15:
        return "⚠️ TESTED — mark well above entry, manage it"
    if pct_of_max < 0 and dte is not None and dte <= 21:
        return f"⏰ {dte} DTE and slightly against — roll/close window"
    if days_held == 0:
        target, label = 25.0, "day-1 rule (25%)"
    elif days_held == 1:
        target, label = 30.0, "day-2 rule (30%)"
    else:
        target, label = 50.0, "50% rule"
    if pct_of_max >= target:
        return f"💰 CLOSE — {pct_of_max:.0f}% captured, hit the {label}"
    if dte is not None and dte <= 21:
        return f"⏰ {dte} DTE — inside the 21-DTE roll/close window"
    return "hold"


def get_positions(session) -> list[dict]:
    """Flat, display-ready list of every open position across accounts."""
    from tastytrade import Account
    today = dt.date.today()
    rows = []
    for acct in _run(Account.get(session)):
        for p in _run(acct.get_positions(session)):
            mult = float(p.multiplier or 1)
            qty = float(p.quantity or 0)
            sign = -1.0 if str(p.quantity_direction).lower().startswith("short") else 1.0
            mark = float(p.mark_price or p.close_price or 0)
            open_price = float(p.average_open_price or 0)
            # For a short option, profit accrues as mark falls toward zero.
            pl = (open_price - mark) * qty * mult if sign < 0 else (mark - open_price) * qty * mult
            pct_of_max = (1 - mark / open_price) * 100 if sign < 0 and open_price > 0 else None

            exp = getattr(p, "expires_at", None)
            dte = expires = None
            if exp is not None:
                exp_date = exp.date() if hasattr(exp, "date") else exp
                try:
                    dte = (exp_date - today).days
                    expires = exp_date.strftime("%m/%d/%Y")
                except (TypeError, AttributeError):
                    pass

            opened = getattr(p, "created_at", None)
            days_held = None
            if opened is not None:
                try:
                    days_held = (today - opened.date()).days
                except (TypeError, AttributeError):
                    pass

            rows.append({
                "account": acct.account_number,
                "symbol": p.symbol,
                "display": pretty_symbol(p.symbol),
                "underlying": str(getattr(p, "underlying_symbol", "") or p.symbol.split()[0]),
                "type": str(p.instrument_type),
                "direction": "SHORT" if sign < 0 else "LONG",
                "qty": qty,
                "open_price": open_price,
                "mark": mark,
                "pl_open": round(pl, 2),
                "pct_of_max_profit": round(pct_of_max, 1) if pct_of_max is not None else None,
                "dte": dte,
                "expires": expires,
                "days_held": days_held,
                "suggestion": position_suggestion(pct_of_max, dte, sign < 0, days_held),
            })
    return rows
