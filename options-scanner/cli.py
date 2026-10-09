#!/usr/bin/env python3
"""Options income scanner — CLI.

Examples:
    python cli.py                          # full scan, live Yahoo data
    python cli.py --demo                   # synthetic data, no network
    python cli.py --tags etf               # ETFs only
    python cli.py --tickers SPY,AAPL,XLE   # explicit watchlist
    python cli.py --max-capital 25000 --min-annual 20
    python cli.py --csv out                # also write out_csps.csv etc.
"""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from scanner import report
from scanner.scan import ScanConfig, rank_dips, run_scan
from scanner.universe import DEFAULT_UNIVERSE, Symbol, filter_universe


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan for CSPs, condors, and broken wing butterflies")
    ap.add_argument("--demo", action="store_true", help="use synthetic data (no network)")
    ap.add_argument("--tasty", action="store_true",
                    help="use live tastytrade data (real-time, incl. futures options); "
                         "needs credentials in .env — see scanner/tastytrade_provider.py")
    ap.add_argument("--timeframe", choices=["5m", "10m", "1h", "4h", "1d"], default="1d",
                    help="candle size for RSI/Bollinger/50-SMA signals (default daily; "
                         "use intraday for scalp hunting)")
    ap.add_argument("--tickers", help="comma-separated watchlist override")
    ap.add_argument("--tags", help="only symbols with any of these tags (comma-separated: etf,blue-chip,dividend,growth,high-iv)")
    ap.add_argument("--min-dte", type=int, default=7)
    ap.add_argument("--max-dte", type=int, default=45)
    ap.add_argument("--delta-min", type=float, default=0.10)
    ap.add_argument("--delta-max", type=float, default=0.35)
    ap.add_argument("--min-annual", type=float, default=12.0, help="min annualized ROC %% for puts")
    ap.add_argument("--max-capital", type=float, help="max cash to secure one put contract")
    ap.add_argument("--min-oi", type=int, default=100)
    ap.add_argument("--limit", type=int, default=20, help="rows per table")
    ap.add_argument("--csv", metavar="PREFIX", help="write PREFIX_csps.csv / _condors.csv / _bwbs.csv / _dips.csv")
    args = ap.parse_args()

    if args.demo:
        from scanner.data import SyntheticProvider
        provider = SyntheticProvider(timeframe=args.timeframe)
    elif args.tasty:
        from scanner.tastytrade_provider import TastytradeProvider
        provider = TastytradeProvider(timeframe=args.timeframe)
    else:
        try:
            from scanner.data import YFinanceProvider
            provider = YFinanceProvider(timeframe=args.timeframe)
        except ImportError:
            print("yfinance not installed — run `pip install -r requirements.txt` "
                  "or use --demo", file=sys.stderr)
            return 1

    universe = DEFAULT_UNIVERSE
    if args.tickers:
        wanted = {t.strip().upper() for t in args.tickers.split(",")}
        known = {s.ticker for s in universe}
        universe = filter_universe(universe, tickers=wanted)
        universe += [Symbol(t, frozenset()) for t in sorted(wanted - known)]
    if args.tags:
        universe = filter_universe(universe, include_tags={t.strip() for t in args.tags.split(",")})
    if not universe:
        print("universe is empty after filters", file=sys.stderr)
        return 1

    cfg = ScanConfig(min_dte=args.min_dte, max_dte=args.max_dte,
                     delta_min=args.delta_min, delta_max=args.delta_max,
                     min_annualized_pct=args.min_annual,
                     max_capital=args.max_capital,
                     min_open_interest=args.min_oi)

    def progress(i, n, ticker):
        print(f"\r  scanning {i + 1}/{n} {ticker:<6}", end="", file=sys.stderr, flush=True)

    result = run_scan(provider, universe, cfg, progress=progress)
    print("", file=sys.stderr)
    dips = rank_dips(result.infos, universe)

    print(report.render_console(result, dips, limit=args.limit))

    if args.csv:
        report.write_csv(f"{args.csv}_csps.csv", report.CSP_HEADERS, report.csp_rows(result.csps, 10**6))
        report.write_csv(f"{args.csv}_condors.csv", report.CONDOR_HEADERS, report.condor_rows(result.condors, 10**6))
        report.write_csv(f"{args.csv}_bwbs.csv", report.BWB_HEADERS, report.bwb_rows(result.bwbs, 10**6))
        report.write_csv(f"{args.csv}_dips.csv", report.DIP_HEADERS, report.dip_rows(dips, 10**6))
        print(f"CSV written with prefix {args.csv}_")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
