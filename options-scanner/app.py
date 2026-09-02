"""Options income scanner — Streamlit dashboard.

Run:  streamlit run app.py
Demo: SCANNER_DEMO=1 streamlit run app.py   (synthetic data, no network)
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner.scan import ScanConfig, dedupe_csps, rank_dips, run_scan
from scanner.universe import DEFAULT_UNIVERSE, Symbol, filter_universe, select_by_tags

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
    # equity sectors (equities/ETFs only — futures never match these)
    "tech", "semis", "financials", "healthcare", "consumer",
    "industrials", "energy", "materials", "utilities", "reits", "china",
    # futures (the only tags that bring futures into a scan)
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
    from scanner import present as _present
    preset_name = st.selectbox(
        "Preset", list(_present.PRESETS), index=0,
        help="One click sets every filter below. Pick Custom to set your own.")
    _p = _present.preset(preset_name)
    if _p.get("blurb"):
        st.caption(_p["blurb"])
    _k = "".join(ch if ch.isalnum() else "_" for ch in preset_name)   # widget keys per preset
    demo = st.toggle("Demo mode (synthetic data)", value=bool(os.environ.get("SCANNER_DEMO")))
    use_tasty = st.toggle("tastytrade live data (real-time, incl. futures)",
                          value=TASTY_AVAILABLE, disabled=not TASTY_AVAILABLE,
                          help="Needs TASTYTRADE_CLIENT_SECRET / TASTYTRADE_REFRESH_TOKEN "
                               "in options-scanner/.env — run `python -m scanner.tastytrade_check`")
    watchlist = st.text_input("Watchlist override (comma-separated)", "")
    with st.expander("Fine-tune", expanded=(preset_name == "Custom")):
        _tfs = ["1d", "4h", "1h", "10m", "5m"]
        timeframe = st.selectbox(
            "Signal timeframe (RSI / Bollinger / 50-SMA)", _tfs,
            index=_tfs.index(_p["timeframe"]), key=f"tf_{_k}",
            help="Daily for swing/wheel entries; drop to 1h–5m to hunt intraday scalp "
                 "setups (oversold bounces at the day's low, etc.)")
        tags = st.multiselect("Universe tags (empty = everything)", ALL_TAGS,
                              default=list(_p["tags"]), key=f"tags_{_k}",
                              help="Sector/style tags scan equities & ETFs only. "
                                   "Pick a futures tag (futures, fut-energy, …) to scan futures.")
        dte = st.slider("Days to expiration", 0, 90, tuple(_p["dte"]), key=f"dte_{_k}")
        delta = st.slider("Put delta range", 0.05, 0.50, tuple(_p["delta"]), step=0.01,
                          key=f"delta_{_k}")
        min_annual = st.number_input("Min annualized ROC %", value=float(_p["min_annual"]),
                                     step=1.0, key=f"annual_{_k}")
        max_capital = st.number_input("Max capital per put ($, 0 = unlimited)", value=0.0, step=5000.0)
        min_oi = st.number_input("Min open interest", value=int(_p["min_oi"]), step=50,
                                 key=f"oi_{_k}")
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
        universe = select_by_tags(universe, set(tags))

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

have_result = st.session_state.result is not None
result = dips = universe = scan_time = None
pulled = ""
if have_result:
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
else:
    st.info("Set your filters in the sidebar and hit **Run scan** — or jump "
            "straight to **⚡ Scalp** for the intraday futures radar (it runs "
            "on its own).")

NEED_SCAN = "Run the income scan first (sidebar → **Run scan**)."

(tab_plan, tab_csp, tab_ic, tab_bwb, tab_dip, tab_scalp, tab_news, tab_score, tab_pos,
 tab_corr) = st.tabs(
    ["📋 Trade Plan", "📉 Puts / Wheel", "🦅 Iron Condors", "🦋 Broken Wing Flies",
     "🔻 Quality Dips", "⚡ Scalp", "📰 News", "📈 Scorecard", "💼 Positions", "🔗 Correlation"])

_tags = {s.ticker: s.tags for s in universe} if have_result else {}
_tags_all = {s.ticker: s.tags for s in DEFAULT_UNIVERSE}   # sector lookup for held names too
import datetime as _dt  # noqa: E402


def _grade_cell(g: dict | None) -> str:
    """One glanceable cell for a track-record grade."""
    if not g:
        return ""
    s = "✅" if g.get("otm") else "❌"
    if g.get("pct_of_max") is not None:
        s += f" {g['pct_of_max']:.0f}%"
    if g.get("tested"):
        s += " ⚠️"
    return s
from scanner.scan import score_bwb, score_condor, score_csp  # noqa: E402
_cfg = ScanConfig()

with tab_plan:
    if not have_result:
        st.info(NEED_SCAN)
    else:
        st.caption(f"The scan, boiled down to actions — generated {pulled}. "
                   "Confirm live premiums before entering. Not financial advice.")

        held_unders: list[str] = []
        rows_all: list[dict] = []
        _checks_out: list = []

        # -- Rulebook first: is the book inside the rules before adding to it? --
        if TASTY_AVAILABLE:
            try:
                from scanner import rules as _rules
                from scanner.tastytrade_provider import (TastytradeProvider as _TP,
                                                         get_balances as _gb,
                                                         get_positions as _gp)
                _tp = _TP()
                rows_all = _gp(_tp.session)
                held_unders = sorted({r["underlying"] for r in rows_all if r.get("underlying")})
                try:
                    _bal = _gb(_tp.session)
                except Exception:
                    _bal = None
                _bd = None
                try:   # SPY-weighted delta from live marks; skipped if quotes fail
                    _spy = _tp.underlying("SPY").spot
                    _bd, _ = _rules.beta_weighted_delta(
                        rows_all,
                        lambda u: _tp.underlying(u).spot,
                        lambda u: _tp.underlying(u).beta, _spy)
                except Exception:
                    pass
                _checks = _rules.check(rows_all, _tags_all, _bal, _bd)
                _checks_out = _checks
                _worst = _rules.worst_status(_checks)
                st.subheader({"breach": "📏 Rulebook — 🔴 outside the rules",
                              "warn": "📏 Rulebook — 🟡 near a limit",
                              "ok": "📏 Rulebook — 🟢 inside the rules"}.get(_worst, "📏 Rulebook"))
                _cols = st.columns(len(_checks))
                for _col, _ck in zip(_cols, _checks):
                    _val = "—" if _ck.value is None else (f"{_ck.value:,.0f}" if abs(_ck.value) >= 100 else f"{_ck.value:g}")
                    _col.metric(f"{_ck.icon} {_ck.name}", _val, help=_ck.detail)
                _bad = [c for c in _checks if c.status in ("breach", "warn")]
                if _bad:
                    st.caption(" · ".join(f"**{c.name}**: {c.detail}" for c in _bad))
            except Exception as exc:
                st.caption(f"Rulebook check unavailable: {exc}")

        # -- What needs attention in the account first, grouped by urgency --
        if TASTY_AVAILABLE:
            try:
                from scanner.tastytrade_provider import TastytradeProvider as _TP, get_positions as _gp
                rows_all = rows_all or _gp(_TP().session)
                closes = [r for r in rows_all if "CLOSE" in r["suggestion"]]
                tested = [r for r in rows_all if "TESTED" in r["suggestion"]]
                windows = [r for r in rows_all if "DTE" in r["suggestion"]
                           and "CLOSE" not in r["suggestion"] and "TESTED" not in r["suggestion"]]

                def _pos_line(r):
                    return (f"**{r['display']}** ({r['direction']} {r['qty']:g}) — "
                            f"open {r['open_price']:g} → mark {r['mark']:g}, "
                            f"P/L {r['pl_open']:+,.0f}")

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

        # -- Book-aware: how each pick sits against what you already hold --
        fit: dict = {}
        if picks and held_unders:
            _fit_key = (tuple(c.ticker for _, c in picks), tuple(held_unders))
            if st.session_state.get("fit_key") == _fit_key:
                fit = st.session_state.get("fit", {})
            else:
                try:
                    from scanner.correlation import candidate_fit
                    fit = candidate_fit([c.ticker for _, c in picks], held_unders)
                except Exception:
                    fit = {}
                st.session_state.fit_key, st.session_state.fit = _fit_key, fit

        def _fit_txt(tk: str) -> str:
            if tk not in fit:
                return ""
            from scanner.correlation import fit_label
            return " · " + fit_label(fit[tk])

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
                vol_txt = ""
                if c.iv_rank is not None:
                    vol_txt += f" · IVR {c.iv_rank:.0f}"
                if c.em_cushion is not None:
                    vol_txt += f" · strike {c.em_cushion:.1f}× the expected move"
                st.caption(f"Ties up \\${c.capital:,.0f} "
                           f"{'margin' if c.is_futures else 'cash'} · "
                           f"{c.downside_protection_pct:.1f}% cushion{vol_txt}{_fit_txt(c.ticker)} · "
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

        # -- Earnings inside 45 days across the candidates and the book --
        import datetime as _dt
        _today = _dt.date.today()
        _earn = []
        for _tk, _info in result.infos.items():
            if _info.next_earnings and 0 <= (_info.next_earnings - _today).days <= 45:
                _earn.append({"Ticker": _tk,
                              "Earnings": _info.next_earnings.strftime("%m/%d/%Y"),
                              "Days": (_info.next_earnings - _today).days,
                              "In book": "✅" if _tk in held_unders else "",
                              "Source": "broker" if _info.iv_source == "tastytrade" else "Yahoo"})
        if _earn:
            st.subheader("📅 Earnings inside 45 days")
            st.caption("No short strike through a report. Anything marked ✅ is a "
                       "position you already hold.")
            st.dataframe(pd.DataFrame(sorted(_earn, key=lambda r: r["Days"])),
                         hide_index=True, use_container_width=True)

        # -- Track record: log today's picks so the Scorecard can grade them --
        if picks:
            from scanner import track as _track
            if st.button("📝 Log today's picks to the track record", key="log_picks",
                         help="Appends the picks above to data/track_record.jsonl. "
                              "Grade them later on the Scorecard tab."):
                _n = _track.record(_track.picks_from_scan(result, _tags))
                st.success(f"Logged {_n} new pick(s). They get graded at 7, 14 and "
                           "30 days and at expiry — see 📈 Scorecard.")

        # -- Alerts: everything above, reduced to act / watch --
        st.subheader("🔔 Alerts")
        from scanner import alerts as _alerts
        _al = _alerts.build_alerts(result, _tags, rows_all, _checks_out)
        if not _al:
            st.write("Nothing needs action.")
        for _a in _al:
            if _a.level == "act":
                st.error(f"{_a.icon} {_a.text}")
            elif _a.level == "watch":
                st.warning(f"{_a.icon} {_a.text}")
            else:
                st.caption(f"{_a.icon} {_a.text}")
        if _al and _alerts.smtp_configured():
            if st.button("📧 Email me these", key="email_alerts"):
                st.info(_alerts.send_email(_al, subject=f"Scanner alerts {pulled}"))

        # -- Print: the same one-page brief the morning routine emails --
        st.subheader("🖨️ Print today's plan")
        try:
            from tools import brief_pdf as _bp
            _brief = _present.brief_from_result(
                result, _tags, picks, _checks_out,
                sorted(_earn, key=lambda r: r["Days"]), scan_time, held_unders)
            _html = _bp.build_html(_brief, _bp.inline_fonts())
            _c1, _c2 = st.columns(2)
            _c1.download_button("Download HTML (open → print)", _html,
                                "trade-plan.html", "text/html", key="plan_html")
            _can_pdf = False
            try:
                import playwright  # noqa: F401
                _can_pdf = _bp.find_chromium() is not None
            except ImportError:
                pass
            if _can_pdf:
                if _c2.button("Build PDF + PNG", key="plan_build"):
                    import pathlib as _pl
                    import tempfile as _tf
                    _out = _pl.Path(_tf.mkdtemp(prefix="plan-"))
                    _pdf, _png = _bp.render(_brief, _out)
                    st.session_state.plan_files = (pulled, _pdf.read_bytes(), _png.read_bytes())
                _pf = st.session_state.get("plan_files")
                if _pf and _pf[0] == pulled:
                    _d1, _d2 = st.columns(2)
                    _d1.download_button("Download PDF", _pf[1], "trade-plan.pdf",
                                        "application/pdf", key="plan_pdf")
                    _d2.download_button("Download PNG", _pf[2], "trade-plan.png",
                                        "image/png", key="plan_png")
            else:
                _c2.caption("PDF needs `playwright` + Chromium on this host; "
                            "the HTML prints from any browser.")
        except Exception as exc:
            st.caption(f"Printable brief unavailable: {exc}")

        st.caption("Exit plan for anything you open: 25% of max on day one, 30% on "
                   "day two, then 50% or the 21-DTE window — same rules the "
                   "Positions tab enforces.")

with tab_csp:
    if not have_result:
        st.info(NEED_SCAN)
    elif not result.csps:
        st.write("No puts passed the filters.")
    else:
        _view = st.radio("View", ["Cards", "Table"], horizontal=True,
                         label_visibility="collapsed", key="csp_view")

        def _day_flag(tk):
            info = result.infos.get(tk)
            if info is None:
                return ""
            if info.at_day_low:
                return "AT LOW"
            if info.at_day_high:
                return "AT HIGH"
            return ""

        if _view == "Cards":
            st.caption("Best strike per name and expiry, ranked by score. "
                       "Switch to **Table** for every column and every strike.")
            for c in dedupe_csps(result.csps)[:10]:
                s_ = score_csp(c, _tags.get(c.ticker, frozenset()), _cfg)
                _chips = _present.chips(c)
                if _day_flag(c.ticker) == "AT LOW":
                    _chips.append("🟢 at day low")
                with st.container(border=True):
                    st.markdown(f"**{_present.verdict(c)}**")
                    st.caption("  ".join(_chips) + f"  ·  score {s_:g}")
                    with st.expander("Details"):
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Annualized", f"{c.annualized_pct:.0f}%")
                        m2.metric("Breakeven", f"{c.breakeven:,.2f}")
                        m3.metric("Cushion", f"{c.downside_protection_pct:.1f}%")
                        m4.metric("Delta / OI", f"{abs(c.delta):.2f} / {c.open_interest:,}")
                        st.caption(f"Spot {c.spot:,.2f} · mid {c.mid:g} · IV {c.iv*100:.0f}% · "
                                   f"{c.dte} DTE · signals: "
                                   f"{', '.join(sorted(c.entry_signals)) or 'none'}")
        else:
            show_all = st.toggle(
                "Show every strike in the delta band", value=False,
                help="Off = the single best-scored strike per ticker & expiry. "
                     "On = the full strike ladder (eight /ES rows at one expiry "
                     "is the same trade at different deltas).")
            csps = result.csps if show_all else dedupe_csps(result.csps)
            df = pd.DataFrame([{
                "Pulled": pulled,
                "Score": score_csp(c, _tags.get(c.ticker, frozenset()), _cfg),
                "Ticker": c.ticker, "Spot": c.spot,
                "RSI": c.rsi_14,
                "IVR": c.iv_rank,
                "Day Lo": result.infos[c.ticker].day_low if c.ticker in result.infos else None,
                "Day Hi": result.infos[c.ticker].day_high if c.ticker in result.infos else None,
                "@Day": _day_flag(c.ticker),
                "Expiry": c.expiry.strftime("%m/%d/%Y"),
                "DTE": c.dte, "Strike": c.strike, "Mid": c.mid,
                "Premium/ct $": c.premium,
                "Capital $": c.capital,
                "Basis": "margin" if c.is_futures else "cash",
                "ROC %": c.roc_pct, "Annualized %": c.annualized_pct,
                "Breakeven": c.breakeven,
                "Cushion %": c.downside_protection_pct,
                "EM $": c.expected_move or None,
                "Strike/EM": c.em_cushion,
                "Delta": abs(c.delta), "P(OTM) %": c.prob_otm_pct,
                "IV %": c.iv * 100, "OI": c.open_interest,
                "Signals": "  ".join(_present.chips(c)),
                "Earnings⚠": c.earnings_before_expiry,
            } for c in csps])
            _num = st.column_config.NumberColumn
            st.dataframe(df, use_container_width=True, hide_index=True, column_config={
                "Score": _num(format="%d"), "Spot": _num(format="%.2f"),
                "RSI": _num(format="%.0f"), "IVR": _num(format="%.0f"),
                "Day Lo": _num(format="%.2f"), "Day Hi": _num(format="%.2f"),
                "Strike": _num(format="%g"), "Mid": _num(format="%.2f"),
                "Premium/ct $": _num(format="$%d"), "Capital $": _num(format="$%d"),
                "ROC %": _num(format="%.2f%%"), "Annualized %": _num(format="%.0f%%"),
                "Breakeven": _num(format="%.2f"), "Cushion %": _num(format="%.1f%%"),
                "EM $": _num(format="%.2f"), "Strike/EM": _num(format="%.2f×"),
                "Delta": _num(format="%.2f"), "P(OTM) %": _num(format="%.0f%%"),
                "IV %": _num(format="%.0f%%"), "OI": _num(format="%d"),
            })
            st.download_button("Download CSV", df.to_csv(index=False), "csps.csv")

with tab_ic:
    if not have_result:
        st.info(NEED_SCAN)
    elif not result.condors:
        st.write("No condors passed the filters.")
    else:
        df = pd.DataFrame([{
            "Score": score_condor(c, _cfg), "Ticker": c.ticker,
            "Spot": round(c.spot, 2), "Expiry": c.expiry.strftime("%m/%d/%Y"), "DTE": c.dte,
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
    if not have_result:
        st.info(NEED_SCAN)
    elif not result.bwbs:
        st.write("No broken wing butterflies passed the filters.")
    else:
        df = pd.DataFrame([{
            "Score": score_bwb(b, _cfg), "Ticker": b.ticker,
            "Spot": round(b.spot, 2), "Expiry": b.expiry.strftime("%m/%d/%Y"), "DTE": b.dte,
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
    if not have_result:
        st.info(NEED_SCAN)
    else:
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

with tab_scalp:
    from scanner.scalp import SCALP_FUTURES, run_scalp_scan
    st.caption("Quick day-trade radar on the deepest futures — runs on its own, "
               "no option chains. LONG/SHORT SCALP = 2 of 3: RSI extreme, "
               "outside the 2σ band, at the session low/high. Signals, not "
               "orders — confirm on the tasty DOM before entering.")
    c1, c2, c3 = st.columns([1, 2, 1])
    scalp_tf = c1.selectbox("Timeframe", ["5m", "10m", "1h"], index=0, key="scalp_tf")
    scalp_syms = c2.multiselect("Products", SCALP_FUTURES, default=SCALP_FUTURES,
                                key="scalp_syms")
    scalp_go = c3.button("⚡ Run scalp scan", type="primary", use_container_width=True)

    if scalp_go:
        source = "demo" if demo else ("tasty" if use_tasty else "yahoo")
        sbar = st.progress(0.0, text="Reading candles…")

        def _sprog(i, n, tk):
            sbar.progress((i + 1) / n, text=f"{tk} ({i + 1}/{n})")

        try:
            rows, errs = run_scalp_scan(scalp_tf, scalp_syms, source=source,
                                        progress=_sprog)
            from datetime import datetime
            from zoneinfo import ZoneInfo
            st.session_state.scalp = (rows, errs,
                                      datetime.now(ZoneInfo("America/New_York")))
        except Exception as exc:
            st.error(f"Scalp scan failed: {exc}")
        sbar.empty()

    if st.session_state.get("scalp"):
        rows, errs, t = st.session_state.scalp
        st.caption(f"🕐 Pulled **{t.strftime('%m/%d %I:%M:%S %p ET')}** — "
                   "futures move fast; re-run before acting.")
        if errs:
            st.warning("No data for: " + ", ".join(f"{k} ({v})" for k, v in errs.items()))
        if not rows:
            st.write("No products returned data.")
        else:
            hot = [r for r in rows if r.bias in ("LONG SCALP", "SHORT SCALP")]
            if hot:
                for r in hot:
                    icon = "🟢" if r.bias == "LONG SCALP" else "🔴"
                    st.markdown(
                        f"{icon} **{r.ticker} {r.bias}** — {r.spot:g}, "
                        f"{' + '.join(sorted(r.signals))} · stop {r.stop:,.2f} · "
                        f"target {r.target:,.2f} (20-bar mean) · "
                        f"risk \\${r.risk_dollars:,.0f}/ct, reward \\${r.reward_dollars:,.0f}/ct "
                        f"(size down with {r.micro})")
            else:
                st.write("**Nothing stretched right now** — no product is 2-of-3. "
                         "That's the answer: don't force a scalp in the middle of the range.")

            _bias_icon = {"LONG SCALP": "🟢 LONG SCALP", "SHORT SCALP": "🔴 SHORT SCALP",
                          "lean long": "↗ lean long", "lean short": "↘ lean short",
                          "no edge": "—"}
            df = pd.DataFrame([{
                "Setup": _bias_icon.get(r.bias, r.bias),
                "Ticker": r.ticker, "Name": r.name,
                "Spot": round(r.spot, 2),
                "Day Lo": round(r.day_low, 2) if r.day_low else None,
                "Day Hi": round(r.day_high, 2) if r.day_high else None,
                "Range %": round(r.range_pos_pct) if r.range_pos_pct is not None else None,
                "RSI": round(r.rsi, 1),
                "Stretch σ": round(r.stretch_sigma, 2),
                "Lower BB": round(r.boll_lower, 2), "Upper BB": round(r.boll_upper, 2),
                "20-bar mean": round(r.mid_band, 2),
                f"ATR ({scalp_tf})": round(r.atr, 2),
                "Stop": round(r.stop, 2) if r.stop is not None else None,
                "Target": round(r.target, 2) if r.target is not None else None,
                "Risk $/ct": round(r.risk_dollars) if r.risk_dollars is not None else None,
                "$/point": r.per_point, "Micro": r.micro,
                "Signals": " + ".join(sorted(r.signals)),
            } for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption("Range % — where price sits in today's range (0 = at the low, "
                       "100 = at the high). Stretch σ — distance from the 20-bar mean "
                       "in standard deviations; ±2 is at the bands. Stop = 0.6×ATR "
                       "past the session extreme; target = the 20-bar mean.")

with tab_score:
    from scanner import track as _track
    st.caption("The scanner grades its own picks. Every logged pick is checked at "
               "7, 14 and 30 days and at expiry: still out of the money, was the "
               "strike ever tested, and how much of the credit the 50% rule would "
               "have captured. This is the number that tells you whether to trust it.")
    _picks = _track.load()
    _c1, _c2 = st.columns([1, 3])
    if _c1.button("🎯 Grade due picks", key="grade_now", disabled=not _picks):
        try:
            if demo:
                from scanner.data import SyntheticProvider as _SP
                _prov = _SP()
            elif use_tasty:
                from scanner.tastytrade_provider import TastytradeProvider as _TP2
                _prov = _TP2()
            else:
                from scanner.data import YFinanceProvider as _YF
                _prov = _YF()
            _n = _track.grade(_picks, _prov)
            _track.save(_picks)
            _c2.success(f"Graded {_n} horizon(s) across {len(_picks)} pick(s).")
        except Exception as exc:
            _c2.error(f"Grading failed: {exc}")
    if not _picks:
        st.info("No picks logged yet. Run a scan, then hit **Log today's picks** on "
                "the Trade Plan tab — or let the morning brief do it automatically.")
    else:
        _sc = _track.scorecard(_picks)
        _m1, _m2, _m3, _m4 = st.columns(4)
        _m1.metric("Picks logged", _sc["picks"])
        _m2.metric("Graded", _sc["graded"])
        _h30 = _sc["by_horizon"].get("30") or {}
        _hx = _sc["by_horizon"].get("expiry") or {}
        _m3.metric("Still OTM at 30d", f"{_h30['otm_pct']:.0f}%" if _h30.get("otm_pct") is not None else "—")
        _m4.metric("Expired worthless", f"{_hx['otm_pct']:.0f}%" if _hx.get("otm_pct") is not None else "—")

        st.markdown("**By horizon**")
        st.dataframe(pd.DataFrame([{
            "Horizon": ("expiry" if h == "expiry" else f"{h} days"),
            "Graded": v["n"],
            "Still OTM %": None if v["otm_pct"] is None else round(v["otm_pct"]),
            "Strike tested %": None if v["tested_pct"] is None else round(v["tested_pct"]),
            "Hit 50% rule %": None if v["hit_50_pct"] is None else round(v["hit_50_pct"]),
            "Avg % of max": None if v["avg_pct_of_max"] is None else round(v["avg_pct_of_max"]),
        } for h, v in _sc["by_horizon"].items()]), hide_index=True, use_container_width=True)

        _l, _r = st.columns(2)
        with _l:
            st.markdown("**By entry signal**")
            st.dataframe(pd.DataFrame([{"Signal": k, "Graded": v["n"],
                                        "Still OTM %": None if v["otm_pct"] is None else round(v["otm_pct"]),
                                        "Tested %": None if v["tested_pct"] is None else round(v["tested_pct"])}
                                       for k, v in _sc["by_signal"].items()]),
                         hide_index=True, use_container_width=True)
        with _r:
            st.markdown("**By sector**")
            st.dataframe(pd.DataFrame([{"Sector": k, "Graded": v["n"],
                                        "Still OTM %": None if v["otm_pct"] is None else round(v["otm_pct"]),
                                        "Tested %": None if v["tested_pct"] is None else round(v["tested_pct"])}
                                       for k, v in _sc["by_sector"].items()]),
                         hide_index=True, use_container_width=True)

        st.markdown("**Every pick**")
        st.dataframe(pd.DataFrame([{
            "Picked": _dt.datetime.fromisoformat(p.picked_on).strftime("%m/%d/%Y"),
            "Ticker": p.ticker, "Strike": p.strike,
            "Expiry": _dt.datetime.fromisoformat(p.expiry).strftime("%m/%d/%Y"),
            "Spot then": p.spot, "Credit $": round(p.premium) if p.mid else None,
            "IVR": None if p.iv_rank is None else round(p.iv_rank),
            "Signals": " + ".join(p.signals), "Score": p.score, "Source": p.source,
            "7d": _grade_cell(p.grades.get("7")), "14d": _grade_cell(p.grades.get("14")),
            "30d": _grade_cell(p.grades.get("30")), "Expiry ": _grade_cell(p.grades.get("expiry")),
        } for p in reversed(_picks)]), hide_index=True, use_container_width=True)
        st.caption("Cells read: ✅ still OTM / ❌ through the strike, then % of max "
                   "credit captured at that point, and ⚠️ if the strike was tested "
                   "at any time since the pick.")

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

                # -- Roll assistant: price the standard repairs for tested shorts --
                _tested = [r for r in rows
                           if "TESTED" in str(r.get("suggestion", ""))
                           and "option" in str(r.get("type", "")).lower()
                           and r.get("expires")]
                if _tested:
                    st.subheader("🔧 Roll assistant")
                    st.caption("For each tested short: the same strike out in time, or one "
                               "strike further out and out in time. Credits first — a debit "
                               "roll is shown, never recommended.")
                    from scanner import roll as _roll
                    from scanner import rules as _rl
                    if demo:
                        from scanner.data import SyntheticProvider as _SP
                        _rp = _SP()
                    elif use_tasty:
                        _rp = TastytradeProvider()
                    else:
                        from scanner.data import YFinanceProvider as _YP
                        _rp = _YP()
                    for r in _tested:
                        _po = _rl.parse_option(r["symbol"])
                        if not _po:
                            continue
                        _exp = _dt.datetime.strptime(r["expires"], "%m/%d/%Y").date()
                        with st.expander(f"{r['display']} — roll options"):
                            try:
                                _rolls = _roll.roll_candidates(
                                    _rp, _po["root"], _po["strike"], _po["is_put"], _exp,
                                    current_mark=float(r["mark"]),
                                    original_credit=float(r["open_price"]))
                            except Exception as exc:
                                st.caption(f"Couldn't price rolls: {exc}")
                                continue
                            if not _rolls:
                                st.write("No expiries 14–60 days further out with quotes.")
                                continue
                            _best = _roll.best_roll(_rolls)
                            if _best:
                                st.success(f"Default: **{_best.label}** → {_best.strike:g} "
                                           f"exp {_best.expiry:%m/%d/%Y} ({_best.dte} DTE) for a "
                                           f"**\\${_best.net_dollars:,.0f} credit**; new breakeven "
                                           f"{_best.new_breakeven:,.2f}.")
                            else:
                                st.warning("Every roll here is a debit — consider taking the "
                                           "loss instead of paying to extend it.")
                            st.dataframe(pd.DataFrame([{
                                "Roll": x.label, "Expiry": x.expiry.strftime("%m/%d/%Y"),
                                "DTE": x.dte, "Strike": x.strike, "New mid": x.new_mid,
                                "Net $": round(x.net_dollars), "Credit?": "✅" if x.is_credit else "❌ debit",
                                "Delta": round(abs(x.delta), 2), "New breakeven": x.new_breakeven,
                                "OI": x.open_interest,
                            } for x in _rolls]), hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(f"Couldn't load positions: {exc}")

with tab_news:
    from scanner import news as _news
    from scanner.rules import futures_root as _fr
    st.caption("Free public feeds — CNBC, MarketWatch, Yahoo Finance, the Federal Reserve — "
               "plus a search for every name you hold or that today's scan picked. "
               "🔴 market-moving · 🟡 notable · ⚪ the rest. Refreshes every 10 minutes; "
               "no scan needed.")

    @st.cache_data(ttl=600, show_spinner="Pulling headlines…")
    def _pull_news(feed_names: tuple, watch: tuple):
        return _news.fetch_all({k: _news.FEEDS[k] for k in feed_names}, list(watch))

    # names to watch: the book (cached 10 min) + today's put candidates + anything typed
    _watch: list[str] = []
    if TASTY_AVAILABLE:
        try:
            _hc = st.session_state.get("held_cache")
            if not _hc or (_dt.datetime.now() - _hc[0]).total_seconds() > 600:
                from scanner.tastytrade_provider import TastytradeProvider as _TPn
                from scanner.tastytrade_provider import get_positions as _gpn
                _hc = (_dt.datetime.now(),
                       sorted({r["underlying"] for r in _gpn(_TPn().session) if r.get("underlying")}))
                st.session_state.held_cache = _hc
            _watch += _hc[1]
        except Exception:
            pass
    if have_result:
        for c in result.csps:
            if c.ticker not in _watch:
                _watch.append(c.ticker)
            if len(_watch) >= 25:
                break
    _n1, _n2, _n3 = st.columns([3, 2, 1])
    _srcs = _n1.multiselect("Feeds", list(_news.FEEDS), default=list(_news.FEEDS), key="news_feeds")
    _extra = _n2.text_input("Also watch (comma-separated)", "", key="news_extra")
    if _n3.button("🔄 Refresh", key="news_refresh"):
        _pull_news.clear()
    for _t in _extra.split(","):
        _t = _t.strip().upper()
        if _t and _t not in _watch:
            _watch.append(_t)
    _watch = list(dict.fromkeys(_fr(t) if t.startswith("/") else t for t in _watch))

    _items, _errs = _pull_news(tuple(_srcs), tuple(_watch))

    def _headline(i):
        t = i.title.replace("[", "(").replace("]", ")").replace("$", "＄")
        meta = " · ".join(x for x in (i.source, i.age()) if x)
        tk = " ".join(f"`{x}`" for x in i.tickers[:4])
        body = f"[{t}]({i.link})" if i.link else t
        st.markdown(f"{i.icon} {body} — {meta} {tk}")

    if _errs:
        st.caption("Couldn't reach: " + ", ".join(sorted(_errs)))
    if not _items:
        st.info("No headlines came back. Check the feed list, or hit Refresh in a minute.")
    else:
        _b = _news.split(_items, _watch)
        st.subheader("🔴 Market-moving")
        if _b["move"]:
            for i in _b["move"][:12]:
                _headline(i)
        else:
            st.write("Nothing big on the tape right now.")
        st.subheader("📌 Your names")
        if _b["mine"]:
            for i in _b["mine"][:20]:
                _headline(i)
        else:
            st.write("No headlines on names you hold or on today's picks.")
        st.subheader("📰 Latest")
        for i in _b["rest"][:30]:
            _headline(i)
        st.caption(f"{len(_items)} headlines · watching " + (", ".join(_watch[:12]) or "nothing yet — run a scan or type a name above"))
