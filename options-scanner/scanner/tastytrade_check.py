"""Validate your tastytrade API setup:  python -m scanner.tastytrade_check

Logs in, pulls one equity chain (SPY) and one futures chain (/ES), prints a
few live quotes and your open positions. If any step fails, paste the error
back to Claude and it'll adjust the provider.
"""

import datetime as dt
import sys


def main() -> int:
    from .tastytrade_provider import TastytradeProvider, get_positions, has_credentials

    if not has_credentials():
        print("Missing credentials. Create options-scanner/.env with:\n"
              "  TASTYTRADE_CLIENT_SECRET=...\n  TASTYTRADE_REFRESH_TOKEN=...\n"
              "from https://developer.tastytrade.com", file=sys.stderr)
        return 1

    provider = TastytradeProvider()
    print("✓ logged in")

    for ticker in ("SPY", "/ES"):
        info = provider.underlying(ticker)
        print(f"✓ {ticker}: spot={info.spot:.2f} RSI={info.rsi_14:.0f} "
              f"expiries={len(info.expiries)}")
        target = dt.date.today() + dt.timedelta(days=30)
        if not info.expiries:
            print(f"  ! no expiries for {ticker}")
            continue
        expiry = min(info.expiries, key=lambda e: abs((e - target).days))
        chain = provider.chain(ticker, expiry)
        otm = [q for q in chain.puts if q.strike < chain.spot and q.mid > 0][-3:]
        print(f"✓ {ticker} {expiry} chain: {len(chain.puts)} puts, "
              f"multiplier={chain.multiplier:g}")
        for q in otm:
            print(f"    {q.strike:g}p bid {q.bid} / ask {q.ask}  IV~{q.iv:.0%}  OI {q.open_interest}")

    positions = get_positions(provider.session)
    print(f"✓ positions: {len(positions)} open")
    for p in positions[:10]:
        print(f"    {p['direction']} {p['qty']:g} {p['symbol']}  "
              f"open {p['open_price']} mark {p['mark']}  P/L {p['pl_open']}")
    print("\nAll good — the scanner can now run on live tastytrade data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
