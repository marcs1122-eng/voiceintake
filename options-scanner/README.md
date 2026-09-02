# 🎯 Options Income Scanner

A personal, free, self-hosted alternative to PowerX Optimizer / Wheel Finder —
built for selling puts, running the wheel, iron condors, and broken wing
butterflies. Covers **stocks, ETFs** (SPY, QQQ, XLE, SMH, TLT, GLD…) **and
options on liquid futures** (/ES /NQ /CL /GC /SI /ZB /ZN /NG /ZC /ZS /ZW /6E),
which the paid tools skip.

Two data sources:
- **Yahoo Finance** (`yfinance`) — free, no API key; stocks/ETFs chains plus
  futures technicals.
- **tastytrade Open API** — free for account holders; real-time chains for
  stocks *and futures options*, plus your live account positions. See
  [tastytrade setup](#tastytrade-setup-real-time--futures--positions).

## What it does

**📉 Puts / Wheel tab** — scans the whole universe for OTM cash-secured puts
in your delta and DTE window and shows every number you need per contract:

- Premium ($/contract) and capital required
- ROC % for the period and **annualized %**
- Breakeven and downside cushion %
- Delta, probability OTM, IV, open interest
- ⚠ flag if earnings land before expiry
- One composite **Score (0–100)** that balances yield vs. safety vs. quality,
  so the top of the list isn't just the junkiest premium

**🦅 Iron Condors tab** — builds a condor per ticker/expiry at your target
short delta (default 16Δ): credit, max loss, ROC, breakevens, and a
lognormal probability-of-profit estimate.

**🦋 Broken Wing Flies tab** — put BWBs below the market (2× short body
around 30Δ, narrow upper wing, wide lower wing). Shows credit/debit, max
profit, max loss, lower breakeven, POP, and whether there's any upside risk
(credit flies have none).

**🔻 Quality Dips tab** — the "which quality names are down the most" radar:
day % change, distance off 52-week high, RSI(14), 50-day SMA, lower Bollinger
Band, next earnings, plus a DipScore for ranking wheel entries.

### Technical entry signals

Every underlying is tagged with put-selling entry signals, shown as a
`Signals` column and baked into the scores (each one lifts a candidate's
rank):

- `RSI<=30` — RSI(14) at or below 30 (oversold)
- `LowerBB` — price at or within 2% of the lower 20-day Bollinger Band (2σ)
- `50SMA` — price sitting at or just above the 50-day SMA (−1%…+3%), i.e.
  selling puts into support rather than into a broken chart

A name flashing all three is a washed-out quality dip sitting on support —
exactly where selling a put pays best.

### Futures options

Futures symbols carry the `futures` tag (`--tags futures` to scan only them).
Their short puts are **margin-secured**: return-on-capital is premium ÷
initial-margin estimate (per product in `scanner/futures.py` — update those
numbers periodically, SPAN margin drifts with volatility), and premium
dollars use the real contract multiplier (/ES $50/pt, /CL $1,000/pt, …).
Chains require the tastytrade provider; with Yahoo only, futures still appear
in the dips radar with entry signals.

### tastytrade setup (real-time + futures + positions)

1. Log into tastytrade → https://developer.tastytrade.com → create an OAuth
   application and grant → copy the client secret and refresh token.
2. `cp .env.example .env` and fill both values (`.env` is git-ignored).
3. Validate: `python -m scanner.tastytrade_check`
4. Run with `python cli.py --tasty` or flip the toggle in the dashboard.

The dashboard also gains a **💼 Positions** tab: every open position with
open price, mark, P/L, and % of max profit captured on short options.

## Quick start

```bash
cd options-scanner
pip install -r requirements.txt

# Dashboard (recommended daily driver)
streamlit run app.py

# Or straight to the terminal
python cli.py                          # full scan
python cli.py --tags etf               # ETFs only
python cli.py --tickers SPY,XLE,AAPL   # your own watchlist
python cli.py --max-capital 25000 --min-annual 20
python cli.py --csv today              # export today_csps.csv etc.

# No internet / just looking at the UI?
python cli.py --demo
SCANNER_DEMO=1 streamlit run app.py
```

## Tuning it to how you trade

- **Universe** — edit `scanner/universe.py`. Every symbol carries tags
  (`etf`, `blue-chip`, `dividend`, `growth`, `high-iv`) so you can scan
  "only stuff I'd be happy to own if assigned."
- **Filters** — everything is in the sidebar (or CLI flags): DTE window,
  delta band, minimum annualized return, max capital per contract, minimum
  open interest, earnings avoidance.
- **Scoring** — the weights live in `scanner/scan.py` (`score_csp`,
  `score_condor`, `score_bwb`) and are deliberately simple to tweak.

## How the numbers are computed

- Prices are **mid** ((bid+ask)/2); always work your own limit orders.
- Yahoo supplies per-contract IV; delta and probabilities are Black-Scholes
  computed in `scanner/bs.py` (risk-neutral lognormal — ranking signals, not
  gospel).
- Liquidity filters (open interest, bid/ask spread %) are applied before
  anything is shown, so unfillable "great" trades don't clutter the list.
- BWB payoff identities are covered by unit tests against a brute-force
  expiry payoff calculation.

## Tests

```bash
python -m pytest tests/ -q
```

## Disclaimers

Yahoo data is delayed ~15 minutes and occasionally has stale quotes on thin
strikes — the OI/spread filters catch most of it. This is a screener, not an
execution tool, and nothing here is financial advice.

## Printable briefs

The scheduled morning brief and scalp-radar pulses are only useful on paper —
`tools/brief_pdf.py` turns a brief into a one-page Letter PDF plus a 276-DPI
PNG (print the PNG when a PDF reader isn't handy; every device prints an
image). Same typography as the Core 20 and Futures reference cards.

```bash
pip install playwright          # Chromium is auto-detected
python3 tools/brief_pdf.py brief.json -o out/
```

The JSON schema is documented in the script's docstring: `title`, `date`,
`pulled`, `lede`, `posture` (futures rows + a one-line read), `candidates`
(ticker / spot / rsi / signals / zone / size), `loud`, `avoid`, `todo`,
`footer`. Every section except title/date is optional and simply omitted
from the sheet when absent.

## News tab

Free public RSS feeds (CNBC, MarketWatch, Yahoo Finance, the Federal Reserve)
plus a Google News search for every name you hold or that today's scan picked.
Headlines are scored — macro words (Fed, CPI, jobs, tariffs, oil) and mentions
of your names score highest — and split into market-moving, your names, and
the rest. No API key; refreshes every 10 minutes. Scoring lives in
`scanner/news.py` and is unit-tested against sample feed data.
