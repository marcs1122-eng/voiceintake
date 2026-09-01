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

# --- Cloud hosting support -------------------------------------------------
# On Streamlit Community Cloud, credentials come from st.secrets instead of a
# local .env; copy them into the environment for the data providers. If a
# DASHBOARD_PASSWORD secret is set, require it before rendering anything —
# apps deployed from public repos are publicly reachable, and this dashboard
# can show live account positions.
_gate = ""
try:
    for _k in ("TASTYTRADE_CLIENT_SECRET", "TASTYTRADE_REFRESH_TOKEN"):
        if _k in st.secrets:
            os.environ.setdefault(_k, str(st.secrets[_k]))
    _gate = str(st.secrets.get("DASHBOARD_PASSWORD", ""))
except Exception:
    pass
if _gate and not st.session_state.get("authed"):
    pw = st.text_input("Password", type="password")
    if pw == _gate:
        st.session_state.authed = True
        st.rerun()
    elif pw:
        st.error("Wrong password.")
    st.stop()

st.title("🎯 Options Income Scanner")
st.caption("Cash-secured puts · wheel · iron condors · broken wing butterflies — "
           "stocks **and** ETFs. Estimates at mid; not financial advice.")

ALL_TAGS = [
    # style / quality
    "etf", "blue-chip", "dividend", "growth", "high-iv",
    # equity sectors
    "tech", "semis", "financials", "healthcare", "consumer",
    "industrials", "energy", "materials", "utilities", "reits", "china",
    # futures
    "futures", "fut-liquid", "uncorrelated", "micro", "fut-index",
    "fut-energy", "fut-metals", "fut-rates", "fut-fx", "fut-ags", "fut-crypto",
]

try:
    from scanner.tastytrade_provider import has_credentials as _tasty_ready
    TASTY_AVAILABLE = _tasty_ready()
except Exception:
    TASTY_AVAILABLE = False

with st.sidebar:
    st.header("Scan settings")
    demo = st.toggle("Demo mode (synthetic data)", value=bool(os.environ.get("SCANNER_DEMO")))
    use_tasty = st.toggle("tastytrade live data (real-time, incl. futures)",
                          value=TASTY_AVAILABLE, disabled=not TASTY_AVAILABLE,
                          help="Needs TASTYTRADE_CLIENT_SECRET / TASTYTRADE_REFRESH_TOKEN "
                               "in options-scanner/.env — run `python -m scanner.tastytrade_check`")
    timeframe = st.selectbox(
        "Signal timeframe (RSI / Bollinger / 50-SMA)",
        ["1d", "4h", "1h", "10m", "5m"], index=0,
        help="Daily for swing/wheel entries; drop to 1h–5m to hunt intraday scalp "
             "setups (oversold bounces at the day's low, etc.)")
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
        provider = SyntheticProvider(timeframe=timeframe)
    elif use_tasty:
        try:
            from scanner.tastytrade_provider import TastytradeProvider
            provider = TastytradeProvider(timeframe=timeframe)
        except Exception as exc:
            st.error(f"tastytrade login failed: {exc}")
            st.stop()
    else:
        try:
            from scanner.data import YFinanceProvider
            provider = YFinanceProvider(timeframe=timeframe)
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
    from datetime import datetime
    from zoneinfo import ZoneInfo
    scan_time = datetime.now(ZoneInfo("America/New_York"))
    st.session_state.result = (result, rank_dips(result.infos, universe), universe, scan_time)

if st.session_state.result is None:
    st.info("Set your filters in the sidebar and hit **Run scan**.")
    st.stop()

result, dips, universe, scan_time = st.session_state.result
pulled = scan_time.strftime("%m/%d %I:%M:%S %p ET")
st.caption(f"🕐 Data pulled: **{pulled}** — snapshot at scan time; hit Run scan to refresh.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Put candidates", len(result.csps))
m2.metric("Iron condors", len(result.condors))
m3.metric("Broken wing flies", len(result.bwbs))
m4.metric("Tickers scanned", len(result.infos))
if result.errors:
    st.warning(f"Skipped (data errors): {', '.join(sorted(result.errors))}")

tab_plan, tab_csp, tab_ic, tab_bwb, tab_dip, tab_pos, tab_corr = st.tabs(
    ["📋 Trade Plan", "📉 Puts / Wheel", "🦅 Iron Condors", "🦋 Broken Wing Flies",
     "🔻 Quality Dips", "💼 Positions", "🔗 Correlation"])

_tags = {s.ticker: s.tags for s in universe}
from scanner.scan import score_bwb, score_condor, score_csp  # noqa: E402
_cfg = ScanConfig()

with tab_plan:
    st.caption(f"The scan, boiled down to actions — generated {pulled}. "
               "Confirm live premiums before entering. Not financial advice.")

    # -- What needs attention in the account first, grouped by urgency --
    if TASTY_AVAILABLE:
        try:
            from scanner.tastytrade_provider import TastytradeProvider as _TP, get_positions as _gp
            rows_all = _gp(_TP().session)
            closes = [r for r in rows_all if "CLOSE" in r["suggestion"]]
            tested = [r for r in rows_all if "TESTED" in r["suggestion"]]
            windows = [r for r in rows_all if "DTE" in r["suggestion"]
                       and "CLOSE" not in r["suggestion"] and "TESTED" not in r["suggestion"]]

            def _pos_line(r):
                return (f"**{r['display']}** ({r['direction']} {r['qty']:g}) — "
                        f"open {r['open_price']:g} → mark {r['mark']:g}, "
                        f"P/L \\${r['pl_open']:,.0f}")

            if closes or tested or windows:
                st.subheader("🔔 Positions needing action")
                if closes:
                    st.success("**Take profits** — hit your ladder:\n\n" +
                               "\n".join(f"- {_pos_line(r)} · {r['suggestion']}" for r in closes))
                if tested:
                    st.error("**Being tested** — decide: defend, roll, or take the loss:\n\n" +
                             "\n".join(f"- {_pos_line(r)}" for r in tested))
                if windows:
                    st.warning("**Inside the 21-DTE window** — roll or close even if healthy:\n\n" +
                               "\n".join(f"- {_pos_line(r)} · {r['suggestion']}" for r in windows))
            else:
                st.subheader("🔔 Positions")
                st.write("Nothing needs action — everything is inside your rules.")
        except Exception:
            pass

    # -- Best new trades: top-scored put per ticker, quality bar applied --
    st.subheader("🎯 Recommended trades to put on")
    seen, picks = set(), []
    for c in result.csps:
        s = score_csp(c, _tags.get(c.ticker, frozenset()), _cfg)
        if c.ticker in seen or s < 70 or c.prob_otm_pct < 65:
            continue
        seen.add(c.ticker)
        picks.append((s, c))
        if len(picks) == 3:
            break
    if not picks:
        st.write("Nothing clears the quality bar right now (score ≥ 70 and "
                 "P(OTM) ≥ 65%). That's an answer too — don't force it.")
    for s, c in picks:
        why = list(sorted(c.entry_signals))
        info = result.infos.get(c.ticker)
        if info is not None and info.at_day_low:
            why.append("at the low of day")
        why_txt = ", ".join(why) if why else "yield + liquidity"
        with st.container(border=True):
            head = f"SELL {c.ticker} {c.strike:g} put · exp {c.expiry:%m/%d/%Y} · {c.dte} DTE"
            if c.earnings_before_expiry:
                head += " · ⚠️ earnings before expiry"
            st.markdown(f"#### {head}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Credit / contract", f"${c.premium:,.0f}")
            m2.metric("Annualized", f"{c.annualized_pct:.0f}%")
            m3.metric("Prob. worthless", f"{c.prob_otm_pct:.0f}%")
            m4.metric("Breakeven", f"{c.breakeven:,.2f}")
            st.caption(f"Ties up \\${c.capital:,.0f} "
                       f"{'margin' if c.is_futures else 'cash'} · "
                       f"{c.downside_protection_pct:.1f}% cushion · "
                       f"why now: {why_txt} · score {s}")

    # -- One defined-risk idea --
    if result.condors:
        ic = result.condors[0]
        with st.container(border=True):
            st.markdown(f"#### 🦅 Defined-risk alternative: {ic.ticker} iron condor · "
                        f"exp {ic.expiry:%m/%d/%Y} · {ic.dte} DTE")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Credit", f"${ic.credit_dollars:,.0f}")
            m2.metric("Max risk", f"${ic.max_loss_dollars:,.0f}")
            m3.metric("Prob. profit", f"{ic.pop_pct:.0f}%")
            m4.metric("Profit zone", f"{ic.breakeven_low:,.0f}–{ic.breakeven_high:,.0f}")
            st.caption(f"Legs: {ic.put_long:g}/{ic.put_short:g} puts — "
                       f"{ic.call_short:g}/{ic.call_long:g} calls")

    st.caption("Exit plan for anything you open: 25% of max on day one, 30% on "
               "day two, then 50% or the 21-DTE window — same rules the "
               "Positions tab enforces.")

with tab_csp:
    if not result.csps:
        st.write("No puts passed the filters.")
    else:
        def _day_flag(tk):
            info = result.infos.get(tk)
            if info is None:
                return ""
            if info.at_day_low:
                return "AT LOW"
            if info.at_day_high:
                return "AT HIGH"
            return ""

        df = pd.DataFrame([{
            "Pulled": pulled,
            "Score": score_csp(c, _tags.get(c.ticker, frozenset()), _cfg),
            "Ticker": c.ticker, "Spot": round(c.spot, 2),
            "RSI": round(c.rsi_14, 1),
            "Day Lo": round(result.infos[c.ticker].day_low, 2) if c.ticker in result.infos else None,
            "Day Hi": round(result.infos[c.ticker].day_high, 2) if c.ticker in result.infos else None,
            "@Day": _day_flag(c.ticker),
            "Expiry": str(c.expiry),
            "DTE": c.dte, "Strike": c.strike, "Mid": c.mid,
            "Premium/ct $": round(c.premium),
            "Capital $": round(c.capital),
            "Basis": "margin" if c.is_futures else "cash",
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
            "Day Lo": round(result.infos[d.ticker].day_low, 2) if d.ticker in result.infos else None,
            "Day Hi": round(result.infos[d.ticker].day_high, 2) if d.ticker in result.infos else None,
            "Day %": d.day_change_pct, "Off 52w high %": d.pct_off_52w_high,
            "RSI(14)": d.rsi_14, "SMA50": round(d.sma_50, 2) if d.sma_50 else None,
            "Lower BB": round(d.boll_lower, 2) if d.boll_lower else None,
            "Signals": " + ".join(sorted(d.entry_signals)),
            "Tags": ", ".join(sorted(d.tags)),
            "Next earnings": str(d.next_earnings) if d.next_earnings else "—",
        } for d in dips])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "dips.csv")

with tab_corr:
    st.caption("PowerX-style asset correlation for YOUR book: how much your "
               "positions move together, where you're doubled up, and what "
               "would actually diversify you. Based on ~3 months of daily closes.")
    extra = st.text_input("Extra symbols to include (comma-separated, optional)", "",
                          key="corr_extra")
    if st.button("🔗 Analyze my positions", key="corr_go"):
        try:
            from scanner import correlation as corr_mod
            unders = []
            if TASTY_AVAILABLE:
                from scanner.tastytrade_provider import TastytradeProvider as _TP, get_positions as _gp
                unders = sorted({r["underlying"] for r in _gp(_TP().session) if r["underlying"]})
            unders += [t.strip().upper() for t in extra.split(",") if t.strip()]
            unders = sorted(set(unders))
            if len(unders) < 2:
                st.warning("Need at least 2 symbols (connect tastytrade or type some in).")
            else:
                with st.spinner(f"Crunching {len(unders)} symbols…"):
                    div_syms = [y for _, y in corr_mod.DIVERSIFIERS if y not in unders]
                    closes = corr_mod.fetch_closes(unders + div_syms)
                    matrix_all = corr_mod.corr_matrix(closes)
                    held = [u for u in unders if u in matrix_all.columns]
                    matrix = matrix_all.loc[held, held]
                    st.session_state.corr = (matrix, matrix_all, held)
        except Exception as exc:
            st.error(f"Correlation analysis failed: {exc}")

    if st.session_state.get("corr") is not None:
        from scanner import correlation as corr_mod
        matrix, matrix_all, held = st.session_state.corr
        stats = corr_mod.analyze(matrix)

        st.metric("Book-wide average correlation", f"{stats['portfolio_avg']:.2f}",
                  help="Average of every pair. 1.0 = everything moves together.")
        st.markdown(f"**{corr_mod.rate_portfolio(stats['portfolio_avg'])}**")

        if stats["hot_pairs"]:
            st.error("**Too correlated — these are effectively the same trade:**\n\n" +
                     "\n".join(f"- {a} ↔ {b}: **{c:.2f}**"
                               for a, b, c in stats["hot_pairs"][:10]))

        top_heavy = [s for s, v in stats["avg_by_symbol"].items() if v >= 0.45][:5]
        if top_heavy:
            st.warning("**Most correlated to the rest of your book** (trimming these "
                       "reduces risk fastest): " + ", ".join(
                           f"{s} ({stats['avg_by_symbol'][s]:.2f})" for s in top_heavy))

        # Diversification ideas: candidates with the lowest avg corr to the book
        ideas = []
        for label, ysym in corr_mod.DIVERSIFIERS:
            if ysym in matrix_all.columns and ysym not in held:
                vals = [matrix_all.loc[ysym, h] for h in held
                        if h in matrix_all.columns and not pd.isna(matrix_all.loc[ysym, h])]
                if vals:
                    ideas.append((label, sum(vals) / len(vals)))
        ideas.sort(key=lambda t: t[1])
        if ideas:
            st.success("**Where to diversify** — lowest correlation to your current book:\n\n" +
                       "\n".join(f"- {label}: avg corr **{v:.2f}**"
                                 for label, v in ideas[:5]))

        def _heat(v):
            if pd.isna(v):
                return ""
            if v >= 0.7:
                return "background-color: rgba(220, 60, 40, 0.55)"
            if v >= 0.4:
                return "background-color: rgba(230, 150, 40, 0.4)"
            if v <= -0.2:
                return "background-color: rgba(40, 160, 90, 0.45)"
            return "background-color: rgba(120, 160, 200, 0.15)"

        st.markdown("**Correlation matrix** (red = moves together, green = offsets):")
        st.dataframe(matrix.style.map(_heat).format("{:.2f}"),
                     use_container_width=True)

with tab_pos:
    st.caption("Live open positions from your tastytrade account (read-only). "
               "For short options, '% of max profit' is how much of the credit "
               "you've already captured — many sellers close at 50%.")
    if not TASTY_AVAILABLE:
        st.info("Connect tastytrade to see positions: put your API credentials in "
                "`options-scanner/.env`, then run `python -m scanner.tastytrade_check`.")
    else:
        try:
            from scanner.tastytrade_provider import TastytradeProvider, get_positions
            rows = get_positions(TastytradeProvider().session)
            if not rows:
                st.write("No open positions.")
            else:
                pos_df = pd.DataFrame(rows).rename(columns={
                    "account": "Account", "display": "Contract", "symbol": "Symbol", "type": "Type",
                    "direction": "Dir", "qty": "Qty", "open_price": "Open",
                    "mark": "Mark", "pl_open": "P/L open $",
                    "pct_of_max_profit": "% of max profit",
                    "dte": "DTE", "expires": "Expires",
                    "days_held": "Held (days)", "suggestion": "Suggestion"})
                cols = ["Suggestion", "Contract", "Dir", "Qty", "Open", "Mark",
                        "P/L open $", "% of max profit", "Held (days)", "DTE",
                        "Expires", "Type", "Account"]
                pos_df = pos_df[[c for c in cols if c in pos_df.columns]]
                st.dataframe(pos_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Couldn't load positions: {exc}")
