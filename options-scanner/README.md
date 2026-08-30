# 🎯 Options Income Scanner

A personal, free, self-hosted alternative to PowerX Optimizer / Wheel Finder —
built for selling puts, running the wheel, iron condors, and broken wing
butterflies. Covers **stocks and ETFs** (SPY, QQQ, XLE, SMH, TLT, GLD…), which
the paid tools skip.

Data comes free from Yahoo Finance via `yfinance` — no API key, no
subscription.

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
day % change, distance off 52-week high, RSI(14), next earnings, plus a
DipScore for ranking wheel entries.

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
