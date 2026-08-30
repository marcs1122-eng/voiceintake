"""Console tables and CSV export for scan results."""

from __future__ import annotations

import csv
import io

from .scan import DipCandidate, ScanResult
from .strategies import BrokenWingButterfly, CashSecuredPut, IronCondor


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "  (no candidates passed the filters)\n"
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    sep = "  ".join("-" * w for w in widths)
    body = "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows)
    return f"{line}\n{sep}\n{body}\n"


def _earn_flag(x: bool) -> str:
    return "⚠ earnings" if x else ""


def csp_rows(csps: list[CashSecuredPut], limit: int = 20) -> list[list[str]]:
    return [[
        c.ticker, f"{c.spot:.2f}", str(c.expiry), str(c.dte),
        f"{c.strike:g}", f"{c.mid:.2f}", f"${c.premium:,.0f}",
        f"{c.roc_pct:.2f}%", f"{c.annualized_pct:.1f}%",
        f"{c.breakeven:.2f}", f"{c.downside_protection_pct:.1f}%",
        f"{abs(c.delta):.2f}", f"{c.prob_otm_pct:.0f}%",
        f"{c.iv * 100:.0f}%", str(c.open_interest),
        "+".join(sorted(c.entry_signals)), _earn_flag(c.earnings_before_expiry),
    ] for c in csps[:limit]]


CSP_HEADERS = ["Ticker", "Spot", "Expiry", "DTE", "Strike", "Mid", "Prem/ct",
               "ROC", "Annual", "B/E", "Cushion", "Delta", "P(OTM)", "IV", "OI",
               "Signals", ""]


def condor_rows(condors: list[IronCondor], limit: int = 15) -> list[list[str]]:
    return [[
        c.ticker, f"{c.spot:.2f}", str(c.expiry), str(c.dte),
        f"{c.put_long:g}/{c.put_short:g}/{c.call_short:g}/{c.call_long:g}",
        f"${c.credit_dollars:,.0f}", f"${c.max_loss_dollars:,.0f}",
        f"{c.roc_pct:.1f}%", f"{c.pop_pct:.0f}%",
        f"{c.breakeven_low:.2f}-{c.breakeven_high:.2f}",
        str(c.min_open_interest), _earn_flag(c.earnings_before_expiry),
    ] for c in condors[:limit]]


CONDOR_HEADERS = ["Ticker", "Spot", "Expiry", "DTE", "Strikes (PL/PS/CS/CL)",
                  "Credit", "MaxLoss", "ROC", "POP", "Breakevens", "MinOI", ""]


def bwb_rows(bwbs: list[BrokenWingButterfly], limit: int = 15) -> list[list[str]]:
    rows = []
    for b in bwbs[:limit]:
        cr = f"${b.credit_dollars:,.0f} cr" if b.net_credit >= 0 else f"${-b.credit_dollars:,.0f} db"
        rows.append([
            b.ticker, f"{b.spot:.2f}", str(b.expiry), str(b.dte),
            f"+1 {b.long_low:g}p / -2 {b.short_mid:g}p / +1 {b.long_high:g}p",
            cr, f"${b.max_profit_dollars:,.0f}", f"${b.max_loss_dollars:,.0f}",
            f"{b.breakeven_low:.2f}", f"{b.pop_pct:.0f}%",
            "none" if not b.upside_risk else "yes", _earn_flag(b.earnings_before_expiry),
        ])
    return rows


BWB_HEADERS = ["Ticker", "Spot", "Expiry", "DTE", "Legs", "Cr/Db", "MaxProfit",
               "MaxLoss", "B/E low", "POP", "UpsideRisk", ""]


def dip_rows(dips: list[DipCandidate], limit: int = 15) -> list[list[str]]:
    return [[
        d.ticker, f"{d.spot:.2f}", f"{d.day_change_pct:+.2f}%",
        f"{d.pct_off_52w_high:.1f}%", f"{d.rsi_14:.0f}",
        f"{d.sma_50:.2f}" if d.sma_50 else "", f"{d.boll_lower:.2f}" if d.boll_lower else "",
        "+".join(sorted(d.entry_signals)),
        f"{d.dip_score:.0f}", ",".join(sorted(d.tags)),
        str(d.next_earnings) if d.next_earnings else "",
    ] for d in dips[:limit]]


DIP_HEADERS = ["Ticker", "Spot", "Day", "Off 52w Hi", "RSI", "SMA50", "LowerBB",
               "Signals", "DipScore", "Tags", "Earnings"]


def render_console(result: ScanResult, dips: list[DipCandidate],
                   limit: int = 20) -> str:
    out = io.StringIO()
    out.write("\n═══ BEST CASH-SECURED PUTS / WHEEL ENTRIES ═══\n")
    out.write(_table(CSP_HEADERS, csp_rows(result.csps, limit)))
    out.write("\n═══ IRON CONDORS ═══\n")
    out.write(_table(CONDOR_HEADERS, condor_rows(result.condors, limit)))
    out.write("\n═══ BROKEN WING BUTTERFLIES (put, credit-style) ═══\n")
    out.write(_table(BWB_HEADERS, bwb_rows(result.bwbs, limit)))
    out.write("\n═══ QUALITY NAMES DOWN THE MOST (put-sale radar) ═══\n")
    out.write(_table(DIP_HEADERS, dip_rows(dips, limit)))
    if result.errors:
        out.write(f"\nSkipped {len(result.errors)} tickers with data errors: "
                  f"{', '.join(sorted(result.errors))}\n")
    out.write("\nMids are estimates; work your own limits. Not financial advice.\n")
    return out.getvalue()


def write_csv(path: str, headers: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([h for h in headers if h])
        for r in rows:
            w.writerow(r)
