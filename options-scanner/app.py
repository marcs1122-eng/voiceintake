"""Options income scanner — Streamlit dashboard.

Run:  streamlit run app.py
Demo: SCANNER_DEMO=1 streamlit run app.py   (synthetic data, no network)
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner.scan import ScanConfig, rank_dips, run_scan
from scanner.universe import DEFAULT_UNIVERSE, Symbol, filter_universe

st.set_page_config(page_title="Options Income Scanner", page_icon="🎯", layout="wide")
st.title("🎯 Options Income Scanner")
st.caption("Cash-secured puts · wheel · iron condors · broken wing butterflies — "
           "stocks **and** ETFs. Estimates at mid; not financial advice.")

ALL_TAGS = ["etf", "blue-chip", "dividend", "growth", "high-iv"]

with st.sidebar:
    st.header("Scan settings")
    demo = st.toggle("Demo mode (synthetic data)", value=bool(os.environ.get("SCANNER_DEMO")))
    tags = st.multiselect("Universe tags (empty = everything)", ALL_TAGS, default=[])
    watchlist = st.text_input("Watchlist override (comma-separated)", "")
    dte = st.slider("Days to expiration", 0, 90, (7, 45))
    delta = st.slider("Put delta range", 0.05, 0.50, (0.10, 0.35), step=0.01)
    min_annual = st.number_input("Min annualized ROC %", value=12.0, step=1.0)
    max_capital = st.number_input("Max capital per put ($, 0 = unlimited)", value=0.0, step=5000.0)
    min_oi = st.number_input("Min open interest", value=100, step=50)
    avoid_earnings = st.toggle("Penalize earnings before expiry", value=True)
    go = st.button("🔍 Run scan", type="primary", use_container_width=True)

if "result" not in st.session_state:
    st.session_state.result = None

if go:
    universe = DEFAULT_UNIVERSE
    if watchlist.strip():
        wanted = {t.strip().upper() for t in watchlist.split(",") if t.strip()}
        known = {s.ticker for s in universe}
        universe = filter_universe(universe, tickers=wanted)
        universe += [Symbol(t, frozenset()) for t in sorted(wanted - known)]
    if tags:
        universe = filter_universe(universe, include_tags=set(tags))

    if demo:
        from scanner.data import SyntheticProvider
        provider = SyntheticProvider()
    else:
        try:
            from scanner.data import YFinanceProvider
            provider = YFinanceProvider()
        except ImportError:
            st.error("yfinance isn't installed. `pip install -r requirements.txt`, "
                     "or flip on Demo mode.")
            st.stop()

    cfg = ScanConfig(min_dte=dte[0], max_dte=dte[1], delta_min=delta[0],
                     delta_max=delta[1], min_annualized_pct=min_annual,
                     max_capital=max_capital or None,
                     min_open_interest=int(min_oi), avoid_earnings=avoid_earnings)

    bar = st.progress(0.0, text="Scanning…")

    def progress(i, n, ticker):
        bar.progress((i + 1) / n, text=f"Scanning {ticker} ({i + 1}/{n})")

    result = run_scan(provider, universe, cfg, progress=progress)
    bar.empty()
    st.session_state.result = (result, rank_dips(result.infos, universe), universe)

if st.session_state.result is None:
    st.info("Set your filters in the sidebar and hit **Run scan**.")
    st.stop()

result, dips, universe = st.session_state.result

m1, m2, m3, m4 = st.columns(4)
m1.metric("Put candidates", len(result.csps))
m2.metric("Iron condors", len(result.condors))
m3.metric("Broken wing flies", len(result.bwbs))
m4.metric("Tickers scanned", len(result.infos))
if result.errors:
    st.warning(f"Skipped (data errors): {', '.join(sorted(result.errors))}")

tab_csp, tab_ic, tab_bwb, tab_dip = st.tabs(
    ["📉 Puts / Wheel", "🦅 Iron Condors", "🦋 Broken Wing Flies", "🔻 Quality Dips"])

_tags = {s.ticker: s.tags for s in universe}
from scanner.scan import score_bwb, score_condor, score_csp  # noqa: E402
_cfg = ScanConfig()

with tab_csp:
    if not result.csps:
        st.write("No puts passed the filters.")
    else:
        df = pd.DataFrame([{
            "Score": score_csp(c, _tags.get(c.ticker, frozenset()), _cfg),
            "Ticker": c.ticker, "Spot": round(c.spot, 2), "Expiry": str(c.expiry),
            "DTE": c.dte, "Strike": c.strike, "Mid": c.mid,
            "Premium/ct $": round(c.premium), "Capital $": round(c.capital),
            "ROC %": round(c.roc_pct, 2), "Annualized %": round(c.annualized_pct, 1),
            "Breakeven": round(c.breakeven, 2),
            "Cushion %": round(c.downside_protection_pct, 1),
            "Delta": round(abs(c.delta), 2), "P(OTM) %": round(c.prob_otm_pct),
            "IV %": round(c.iv * 100), "OI": c.open_interest,
            "Signals": " + ".join(sorted(c.entry_signals)),
            "Earnings⚠": c.earnings_before_expiry,
        } for c in result.csps])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "csps.csv")

with tab_ic:
    if not result.condors:
        st.write("No condors passed the filters.")
    else:
        df = pd.DataFrame([{
            "Score": score_condor(c, _cfg), "Ticker": c.ticker,
            "Spot": round(c.spot, 2), "Expiry": str(c.expiry), "DTE": c.dte,
            "Put wing": f"{c.put_long:g}/{c.put_short:g}",
            "Call wing": f"{c.call_short:g}/{c.call_long:g}",
            "Credit $": round(c.credit_dollars), "Max loss $": round(c.max_loss_dollars),
            "ROC %": round(c.roc_pct, 1), "POP %": round(c.pop_pct),
            "BE low": round(c.breakeven_low, 2), "BE high": round(c.breakeven_high, 2),
            "Min OI": c.min_open_interest, "Earnings⚠": c.earnings_before_expiry,
        } for c in result.condors])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "condors.csv")

with tab_bwb:
    if not result.bwbs:
        st.write("No broken wing butterflies passed the filters.")
    else:
        df = pd.DataFrame([{
            "Score": score_bwb(b, _cfg), "Ticker": b.ticker,
            "Spot": round(b.spot, 2), "Expiry": str(b.expiry), "DTE": b.dte,
            "Legs": f"+1 {b.long_low:g}p / -2 {b.short_mid:g}p / +1 {b.long_high:g}p",
            "Credit(+)/Debit(-) $": round(b.net_credit * 100),
            "Max profit $": round(b.max_profit * 100),
            "Max loss $": round(max(b.max_loss, 0) * 100),
            "BE low": round(b.breakeven_low, 2), "POP %": round(b.pop_pct),
            "Upside risk": "yes" if b.upside_risk else "none",
            "Earnings⚠": b.earnings_before_expiry,
        } for b in result.bwbs])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "bwbs.csv")

with tab_dip:
    st.caption("Quality names most washed out — candidates to start the wheel on. "
               "DipScore blends today's drop, distance off the 52-week high, RSI, "
               "and the entry signals: RSI≤30, lower Bollinger Band touch, 50-SMA support.")
    if not dips:
        st.write("No dip candidates.")
    else:
        df = pd.DataFrame([{
            "DipScore": d.dip_score, "Ticker": d.ticker, "Spot": round(d.spot, 2),
            "Day %": d.day_change_pct, "Off 52w high %": d.pct_off_52w_high,
            "RSI(14)": d.rsi_14, "SMA50": round(d.sma_50, 2) if d.sma_50 else None,
            "Lower BB": round(d.boll_lower, 2) if d.boll_lower else None,
            "Signals": " + ".join(sorted(d.entry_signals)),
            "Tags": ", ".join(sorted(d.tags)),
            "Next earnings": str(d.next_earnings) if d.next_earnings else "—",
        } for d in dips])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "dips.csv")
