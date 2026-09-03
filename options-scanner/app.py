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

# --- Look & feel ------------------------------------------------------------
st.markdown("""
<style>
.hero{background:linear-gradient(120deg,#0f172a 0%,#1e3a8a 60%,#2563eb 100%);color:#fff;
      border-radius:16px;padding:18px 24px;margin:-10px 0 10px}
.hero h1{margin:0;font-size:1.9rem;color:#fff;letter-spacing:.01em}
.hero p{margin:4px 0 0;opacity:.85;font-size:.95rem}
div[data-testid="stMetric"]{background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:10px 14px}
button[data-baseweb="tab"]{font-size:1rem;font-weight:600}
.pcard{border:1px solid #e3e8ef;border-left:6px solid #94a3b8;border-radius:12px;padding:14px 18px;
       margin:10px 0;background:#fff;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.pcard.hi{border-left-color:#16a34a;background:linear-gradient(90deg,#f0fdf4 0,#fff 35%)}
.pcard.mid{border-left-color:#f59e0b;background:linear-gradient(90deg,#fffbeb 0,#fff 35%)}
.pc-head{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.pc-tk{font-weight:800;font-size:1.25rem;letter-spacing:.02em;color:#0f172a}
.pc-verdict{flex:1;font-size:1.02rem;color:#1f2937;min-width:240px}
.pc-score{font-weight:700;background:#111827;color:#fff;border-radius:999px;padding:3px 12px;font-size:.9rem}
.pc-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin:12px 0 8px}
.pc-stats div{background:#f8fafc;border-radius:10px;padding:8px 10px}
.pc-stats b{display:block;font-size:1.2rem;color:#0f172a}
.pc-stats small{color:#64748b;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.chip{display:inline-block;border-radius:999px;padding:2px 10px;margin:2px 4px 0 0;font-size:.8rem;
      background:#f1f5f9;color:#475569;border:1px solid #e2e8f0}
.chip.on{background:#dcfce7;color:#166534;border-color:#bbf7d0}
.chip.warn{background:#fef3c7;color:#92400e;border-color:#fde68a}
.chip.bad{background:#fee2e2;color:#991b1b;border-color:#fecaca}
.pc-why{color:#475569;font-size:.85rem;margin-top:6px}
.pos-line{padding:6px 10px;border-radius:8px;margin:3px 0;background:#f8fafc;border:1px solid #e5e7eb}
</style>
<div class="hero"><h1>🎯 Options Income Scanner</h1>
<p>Cash-secured puts · wheel · iron condors · broken wing butterflies · futures · scalp radar — estimates at mid; not financial advice.</p></div>
""", unsafe_allow_html=True)

ALL_TAGS = [
    # style / quality
    "etf", "blue-chip", "dividend", "growth", "high-iv", "leveraged",
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

def _make_provider(tf: str):
    """Demo → synthetic; tastytrade when enabled; else Yahoo. Stops the app with
    a readable message when the chosen source cannot start."""
    if demo:
        from scanner.data import SyntheticProvider
        return SyntheticProvider(timeframe=tf)
    if use_tasty:
        try:
            from scanner.tastytrade_provider import TastytradeProvider
            return TastytradeProvider(timeframe=tf)
        except Exception as exc:
            st.error(f"tastytrade login failed: {exc}")
            st.stop()
    try:
        from scanner.data import YFinanceProvider
        return YFinanceProvider(timeframe=tf)
    except ImportError:
        st.error("yfinance isn't installed. `pip install -r requirements.txt`, "
                 "or flip on Demo mode.")
        st.stop()


def _tasty():
    """One tastytrade session per browser session (login is slow; never redo it per rerun)."""
    if not TASTY_AVAILABLE:
        return None
    tp = st.session_state.get("tasty")
    if tp is None:
        from scanner.tastytrade_provider import TastytradeProvider
        tp = TastytradeProvider(timeframe="1d")
        st.session_state.tasty = tp
    return tp


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
                              help="Sector/style tags scan equities & ETFs only. 'leveraged' = the 2-3x "
                                   "and inverse ETFs (TQQQ, SOXL, SPXL …), only when asked for. "
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

    st.session_state.pop("diversify_note", None)
    if _p.get("diversify"):
        _held0: list[str] = []
        _tp0 = _tasty() if not demo else None
        if _tp0 is not None:
            try:
                from scanner.tastytrade_provider import get_positions as _gp0
                _held0 = sorted({r["underlying"] for r in _gp0(_tp0.session) if r.get("underlying")})
            except Exception:
                pass
        try:
            from scanner import correlation as _corr0
            with st.spinner("Finding what diversifies your book…"):
                _ideas = (_corr0.diversification_ideas(_held0) if _held0
                          else [(l, y, 0.0) for l, y in _corr0.DIVERSIFIERS])
            _known = {sym.ticker for sym in DEFAULT_UNIVERSE}
            _names = _present.diversify_universe([(y, v) for _, y, v in _ideas], _known)
            universe = filter_universe(DEFAULT_UNIVERSE, tickers=set(_names))
            universe += [Symbol(t, frozenset({"futures"})) for t in _names if t not in _known]
            st.session_state.diversify_note = (
                "Diversify scan — " + ", ".join(_names) + ". Lowest correlation to your book: "
                + ", ".join(f"{l} {v:.2f}" for l, _, v in _ideas[:4])
                + ("" if _held0 else " (no live positions found, so every diversifier was used)"))
        except Exception as exc:
            st.warning(f"Couldn't work out the diversifiers ({exc}); scanning the whole universe.")

    provider = _make_provider(timeframe)

    cfg = ScanConfig(min_dte=dte[0], max_dte=dte[1], delta_min=delta[0],
                     delta_max=delta[1], min_annualized_pct=min_annual,
                     max_capital=max_capital or None,
                     min_open_interest=int(min_oi), avoid_earnings=avoid_earnings,
                     max_gap_pct=_p.get("gap"))

    bar = st.progress(0.0, text="Scanning…")

    def progress(i, n, ticker):
        bar.progress((i + 1) / n, text=f"Scanning {ticker} ({i + 1}/{n})")

    result = run_scan(provider, universe, cfg, progress=progress)
    bar.empty()
    from datetime import datetime
    from zoneinfo import ZoneInfo
    scan_time = datetime.now(ZoneInfo("America/New_York"))
    st.session_state.result = (result, rank_dips(result.infos, universe), universe, scan_time)
    st.session_state.provider = provider
    st.session_state.preset_used = preset_name
    st.session_state.pop("plan_ctx", None)

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
if st.session_state.get("diversify_note") and have_result:
    st.caption("🧭 " + st.session_state.diversify_note)

_tags = {s.ticker: s.tags for s in universe} if have_result else {}
_tags_all = {s.ticker: s.tags for s in DEFAULT_UNIVERSE}   # sector lookup for held names too
import datetime as _dt  # noqa: E402
import html as _html  # noqa: E402
from scanner.scan import score_bwb, score_condor, score_csp  # noqa: E402
_cfg = ScanConfig()
_TOP_N = int(_p.get("top_n") or 10)

TAB_HELP = {
    "plan": ("📋 Trade Plan", "Everything from the scan boiled down to actions: are you inside your "
             "rules, what needs managing in the book, the top-ranked setups, earnings to avoid, "
             "alerts, and the print button."),
    "bounce": ("🏀 Bounce / 🪂 Fade", "Daily-chart extremes for 1-3 day trades. Bounce: RSI 32 or "
               "under, at or through the lower Bollinger Band, down 2% today or 8% on the week, "
               "within 10% of the 200-day, no earnings this week → sell the 0.20-0.25 delta put. "
               "Fade: RSI 70 or over, at or through the upper band, up 2% today or 8% on the week "
               "→ sell a 0.20-0.25 delta call credit spread. Close in a day or three. Near-misses "
               "are shown with the reason they missed."),
    "csp": ("📉 Puts / Wheel", "Cash- or margin-secured puts that passed your filters. Cards = plain "
            "English on the best strike per name. Table = every column and every strike. Score blends "
            "yield, probability, IV Rank, expected-move cushion and the technicals."),
    "ic": ("🦅 Iron Condors", "Defined risk on both sides: a short put spread and a short call spread "
           "placed around the expected move. Best when IV Rank is high and the chart is range-bound."),
    "bwb": ("🦋 Broken Wing Flies", "A butterfly with one wing wider so it goes on for a small credit "
            "or near zero cost: profits in a zone, with little or no risk on one side."),
    "dip": ("🔻 Quality Dips", "Blue chips and big ETFs that are washed out: RSI, distance below the "
            "50-day and the lower band. The wheel's shopping list."),
    "scalp": ("⚡ Scalp", "Intraday radar on the most liquid futures: RSI extremes, 2-sigma band "
              "breaks and the day's low/high on 5m to 1h bars, with a stop and a target sized in "
              "dollars. Runs on its own, no scan needed."),
    "news": ("📰 News", "Free feeds scored for what moves premium sellers: Fed, CPI, jobs, tariffs, "
             "oil, and anything naming a ticker you hold or that today's scan picked."),
    "score": ("📈 Scorecard", "Your track record. Every logged pick graded at 7, 14 and 30 days and at "
              "expiry: did it stay out of the money, how much of the credit it captured, was it tested."),
    "pos": ("💼 Positions", "Live positions grouped into the structures you actually sold (a strangle "
            "is one trade, not two legs), with real breakevens on the total credit and the "
            "management call: close, roll forward, roll the untested side, or hold."),
    "corr": ("🔗 Correlation", "How much your positions move together over the last three months, "
             "which pairs are the same trade, and what would actually diversify you."),
}


def _card_html(c, score: float, at_low: bool = False, extra: str = "") -> str:
    """A colored trade card. Dollar signs go in as entities so Streamlit's
    markdown never mistakes them for math."""
    cls = "hi" if score >= 85 else ("mid" if score >= 75 else "")
    chips = []
    for ch in _present.chips(c):
        kind = "on" if ch.startswith("🟢") else ("warn" if ch.startswith("🟡") else ("bad" if ch.startswith("🔴") else ""))
        chips.append(f'<span class="chip {kind}">{_html.escape(ch[1:].strip())}</span>')
    if at_low:
        chips.append('<span class="chip on">at day low</span>')
    verdict = _html.escape(_present.verdict(c)).replace("$", "&#36;")
    why = _html.escape(_present.why(c, at_low)) + _html.escape(extra)
    basis = "margin" if c.is_futures else "cash"
    return (f'<div class="pcard {cls}"><div class="pc-head"><span class="pc-tk">{_html.escape(c.ticker)}</span>'
            f'<span class="pc-verdict">{verdict}</span><span class="pc-score">{score:g}</span></div>'
            f'<div class="pc-stats">'
            f'<div><b>&#36;{c.premium:,.0f}</b><small>credit / contract</small></div>'
            f'<div><b>{c.annualized_pct:.0f}%</b><small>annualized</small></div>'
            f'<div><b>{c.prob_otm_pct:.0f}%</b><small>keeps the credit</small></div>'
            f'<div><b>{c.breakeven:,.2f}</b><small>breakeven</small></div>'
            f'<div><b>{c.downside_protection_pct:.1f}%</b><small>cushion</small></div>'
            f'<div><b>&#36;{c.capital:,.0f}</b><small>{basis} tied up</small></div>'
            f'</div><div class="pc-chips">{"".join(chips)}</div>'
            f'<div class="pc-why">why now: {why} · {c.dte} DTE · exp {c.expiry:%m/%d/%Y}</div></div>')


def _tab_head(key: str) -> None:
    title, text = TAB_HELP[key]
    st.markdown(f"##### {title}", help=text)


def _plan_ctx() -> dict:
    """Everything the Trade Plan, Positions, Alerts and Print need, computed
    ONCE per scan and kept in the session — so switching a tab or a toggle
    never re-hits the broker (that was the minute-long freeze)."""
    key = pulled
    ctx = st.session_state.get("plan_ctx")
    if ctx and ctx.get("key") == key:
        return ctx
    ctx = {"key": key, "rows": [], "held": [], "bal": None, "spots": {}, "structs": [],
           "checks": [], "bd": None, "picks": [], "fit": {}, "earn": [], "alerts": [],
           "errors": [], "when": _dt.datetime.now()}
    _tp = _tasty() if not demo else None
    if _tp is not None:
        try:
            from scanner import positions as _positions
            from scanner import rules as _rules
            from scanner.tastytrade_provider import get_balances as _gb, get_positions as _gp
            rows = _gp(_tp.session)
            ctx["rows"] = rows
            ctx["held"] = sorted({r["underlying"] for r in rows if r.get("underlying")})
            try:
                ctx["bal"] = _gb(_tp.session)
            except Exception as exc:
                ctx["errors"].append(f"balances: {exc}")
            try:
                ctx["spots"] = _tp.spots(ctx["held"] + ["SPY"])
            except Exception as exc:
                ctx["errors"].append(f"quotes: {exc}")
            ctx["structs"] = _positions.build(rows, spot_of=ctx["spots"].get)
            try:
                spy = ctx["spots"].get("SPY")
                if spy:
                    ctx["bd"], _ = _rules.beta_weighted_delta(rows, ctx["spots"].get, _tp.beta, spy)
            except Exception as exc:
                ctx["errors"].append(f"beta-delta: {exc}")
            ctx["checks"] = _rules.check(rows, _tags_all, ctx["bal"], ctx["bd"])
        except Exception as exc:
            ctx["errors"].append(f"positions: {exc}")
    if have_result:
        seen, picks = set(), []
        for c in result.csps:
            sc = score_csp(c, _tags.get(c.ticker, frozenset()), _cfg)
            if c.ticker in seen or sc < 70 or c.prob_otm_pct < 65:
                continue
            seen.add(c.ticker)
            picks.append((sc, c))
            if len(picks) == (5 if _p.get("top_n") else 3):
                break
        ctx["picks"] = picks
        if picks and ctx["held"]:
            try:
                from scanner.correlation import candidate_fit
                ctx["fit"] = candidate_fit([c.ticker for _, c in picks], ctx["held"])
            except Exception:
                ctx["fit"] = {}
        today = _dt.date.today()
        for tk, info in result.infos.items():
            if info.next_earnings and 0 <= (info.next_earnings - today).days <= 45:
                ctx["earn"].append({"Ticker": tk,
                                    "Earnings": info.next_earnings.strftime("%m/%d/%Y"),
                                    "Days": (info.next_earnings - today).days,
                                    "In book": "✅" if tk in ctx["held"] else "",
                                    "Source": "broker" if info.iv_source == "tastytrade" else "Yahoo"})
        ctx["earn"].sort(key=lambda r: r["Days"])
        from scanner import alerts as _alerts
        pos_rows = [{"underlying": x.underlying, "display": x.display, "suggestion": x.suggestion}
                    for x in ctx["structs"]]
        ctx["alerts"] = _alerts.build_alerts(result, _tags, pos_rows, ctx["checks"])
    st.session_state.plan_ctx = ctx
    return ctx


def _print_block(key: str) -> None:
    """The one-page brief: preview with a browser Print button (works on any
    host), HTML download, and PDF + PNG when Chromium is available."""
    if not have_result:
        st.caption(NEED_SCAN)
        return
    try:
        from tools import brief_pdf as _bp
        ctx = _plan_ctx()
        brief = _present.brief_from_result(result, _tags, ctx["picks"], ctx["checks"],
                                           ctx["earn"], scan_time, ctx["held"])
        page = _bp.build_html(brief, _bp.inline_fonts())
    except Exception as exc:
        st.caption(f"Printable brief unavailable: {exc}")
        return
    c1, c2, c3 = st.columns([2, 2, 3])
    show = c1.toggle("🖨️ Preview + print", value=False, key=f"{key}_prev",
                     help="Opens the one-page plan below with a Print button. Print → Save as PDF "
                          "works in every browser, phone included.")
    c2.download_button("⬇️ HTML file", page, "trade-plan.html", "text/html", key=f"{key}_html",
                       help="Open it in any browser and print from there.")
    can_pdf = False
    try:
        import playwright  # noqa: F401
        can_pdf = _bp.find_chromium() is not None
    except ImportError:
        pass
    if can_pdf:
        if c3.button("Build PDF + PNG", key=f"{key}_build"):
            import pathlib as _pl
            import tempfile as _tf
            out = _pl.Path(_tf.mkdtemp(prefix="plan-"))
            pdf, png = _bp.render(brief, out)
            st.session_state.plan_files = (pulled, pdf.read_bytes(), png.read_bytes())
        pf = st.session_state.get("plan_files")
        if pf and pf[0] == pulled:
            d1, d2 = st.columns(2)
            d1.download_button("⬇️ PDF", pf[1], "trade-plan.pdf", "application/pdf", key=f"{key}_pdf")
            d2.download_button("⬇️ PNG", pf[2], "trade-plan.png", "image/png", key=f"{key}_png")
    else:
        c3.caption("Use Preview + print → your browser's Print → Save as PDF.")
    if show:
        import streamlit.components.v1 as components
        btn = ('<style>@media print{.noprint{display:none!important}}</style>'
               '<div class="noprint" style="text-align:right;margin:6px 0 10px">'
               '<button onclick="window.print()" style="font-size:16px;padding:9px 20px;'
               'border-radius:8px;background:#1e3a8a;color:#fff;border:0;cursor:pointer">'
               '🖨️ Print / Save as PDF</button></div>')
        components.html(page.replace("<body>", "<body>" + btn, 1), height=1150, scrolling=True)


if have_result:
    with st.expander("🖨️ Print today's plan", expanded=False):
        _print_block("top")

(tab_plan, tab_bounce, tab_csp, tab_ic, tab_bwb, tab_dip, tab_scalp, tab_news, tab_score,
 tab_pos, tab_corr) = st.tabs(
    ["📋 Trade Plan", "🏀 Bounce", "📉 Puts / Wheel", "🦅 Iron Condors", "🦋 Broken Wing Flies",
     "🔻 Quality Dips", "⚡ Scalp", "📰 News", "📈 Scorecard", "💼 Positions", "🔗 Correlation"])


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

with tab_plan:
    _tab_head("plan")
    if not have_result:
        st.info(NEED_SCAN)
    else:
        st.caption(f"The scan, boiled down to actions — generated {pulled}. "
                   "Confirm live premiums before entering. Not financial advice.")
        _ctx = _plan_ctx()
        from scanner import positions as _positions
        from scanner import rules as _rules
        for _e in _ctx["errors"]:
            st.caption(f"⚠️ {_e}")

        # -- Rulebook first: is the book inside the rules before adding to it? --
        if _ctx["checks"]:
            _checks = _ctx["checks"]
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

        # -- What needs attention in the book, by urgency, as STRUCTURES --
        _structs = _ctx["structs"]
        if _structs:
            _by = {}
            for _s in _structs:
                _by.setdefault(_s.status, []).append(_s)

            def _pos_line(x):
                return (f"- **{x.display}** — {x.suggestion} · P/L {x.pl_open:+,.0f}")

            _need = [k for k in ("breached", "tested", "close", "roll_forward", "window") if _by.get(k)]
            if _need:
                st.subheader("🔔 Positions needing action")
                if _by.get("breached"):
                    st.error("**Breakeven breached** — defend or take the loss:\n\n" +
                             "\n".join(_pos_line(x) for x in _by["breached"]))
                if _by.get("tested"):
                    st.warning("**Being tested** — strike touched, still inside the breakeven. For a "
                               "strangle, roll the *untested* side in toward its original delta:\n\n" +
                               "\n".join(_pos_line(x) for x in _by["tested"]))
                if _by.get("close"):
                    st.success("**Take profits** — hit your ladder:\n\n" +
                               "\n".join(_pos_line(x) for x in _by["close"]))
                if _by.get("roll_forward"):
                    st.info("**Roll forward** — 25%+ captured: bank it and add time:\n\n" +
                            "\n".join(_pos_line(x) for x in _by["roll_forward"]))
                if _by.get("window"):
                    st.warning("**Inside the 21-DTE window** — roll or close even if healthy:\n\n" +
                               "\n".join(_pos_line(x) for x in _by["window"]))
            else:
                st.subheader("🔔 Positions")
                st.write("Nothing needs action — everything is inside your rules.")
            _holds = _by.get("hold", [])
            if _holds:
                with st.expander(f"🟢 Holding fine ({len(_holds)})"):
                    st.markdown("\n".join(_pos_line(x) for x in _holds))

        # -- Best new setups: top-scored put per ticker, quality bar applied --
        st.subheader("🎯 Top-ranked setups")
        picks = _ctx["picks"]
        if not picks:
            st.write("Nothing clears the quality bar right now (score ≥ 70 and "
                     "P(OTM) ≥ 65%). That's an answer too — don't force it.")
        fit = _ctx["fit"]

        def _fit_txt(tk: str) -> str:
            if tk not in fit:
                return ""
            from scanner.correlation import fit_label
            return " · " + fit_label(fit[tk])

        for s_, c in picks:
            info = result.infos.get(c.ticker)
            st.markdown(_card_html(c, s_, bool(info and info.at_day_low), _fit_txt(c.ticker)),
                        unsafe_allow_html=True)

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
        if _ctx["earn"]:
            st.subheader("📅 Earnings inside 45 days")
            st.caption("No short strike through a report. Anything marked ✅ is a "
                       "position you already hold.")
            st.dataframe(pd.DataFrame(_ctx["earn"]), hide_index=True, use_container_width=True)

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
        _al = _ctx["alerts"]
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

        st.subheader("🖨️ Print today's plan")
        _print_block("plan")

        st.caption("Exit plan for anything you open: 25% of max on day one, 30% on "
                   "day two, then 50% or the 21-DTE window — same rules the "
                   "Positions tab enforces.")

with tab_bounce:
    _tab_head("bounce")
    from scanner import bounce as _bounce
    st.caption("Runs on its own — no income scan needed. Universe: every stock in the scanner's "
               "large-cap universe, the 18 bounce ETFs, and the 8 futures roots. Banned names "
               "(CRDO SLV AAL NFLX) are dropped; semis are flagged scalp-only, never dropped.")
    _b_dir = st.radio("Direction", ["🏀 Bounce — RSI ≤ 32, sell puts", "🪂 Fade — RSI ≥ 70, call credit spreads", "Both"],
                      horizontal=True, key="b_dir",
                      help="Daily chart. Bounce = washed out at the lower band, sell a 0.20-0.25Δ put. "
                           "Fade = overbought at the upper band, sell a 0.20-0.25Δ call spread (never naked).")
    with st.expander("Bounce settings"):
        _b1, _b2, _b3, _b4 = st.columns(4)
        _b_rsi = _b1.number_input("RSI ≤ (bounce)", value=32.0, step=1.0, key="b_rsi")
        _b_rsi_hi = _b1.number_input("RSI ≥ (fade)", value=70.0, step=1.0, key="b_rsi_hi")
        _b_vol = _b1.number_input("Min 10-day avg volume (M)", value=1.0, step=0.5, key="b_vol")
        _b_band = _b2.number_input("Band tolerance % above", value=1.0, step=0.5, key="b_band")
        _b_day = _b3.number_input("Day drop ≤ %", value=-2.0, step=0.5, key="b_day")
        _b_week = _b4.number_input("5-day drop ≤ %", value=-8.0, step=1.0, key="b_week")
        _b5, _b6, _b7, _b8 = st.columns(4)
        _b_sma = _b5.number_input("Max % below 200-day", value=-10.0, step=1.0, key="b_sma")
        _b_earn = _b6.number_input("Earnings-free trading days", value=5, step=1, key="b_earn")
        _b_dte = _b7.slider("DTE", 14, 60, (30, 45), key="b_dte")
        _b_delta = _b8.slider("Put delta", 0.10, 0.40, (0.20, 0.25), step=0.01, key="b_delta")
        _b_near = st.toggle("Show near-misses (RSI passes, band within 6%) with the reason", value=True, key="b_near")
        _b_lev = st.toggle("Include leveraged ETFs (TQQQ SOXL SPXL TNA LABU NUGT UCO BOIL TMF …)",
                           value=False, key="b_lev",
                           help="2-3x products decay, so the 200-day rule is loose on them; they are "
                                "flagged LEVERAGED and belong to day trades only.")
    if st.button("🏀 Run BOUNCE scan", type="primary", key="b_go"):
        _bcfg = _bounce.BounceConfig(direction={"🏀": "bounce", "🪂": "fade"}.get(_b_dir[:1], "both"),
                                     rsi_max=_b_rsi, rsi_min_fade=_b_rsi_hi,
                                     min_avg_volume=float(_b_vol) * 1e6,
                                     band_tol_pct=_b_band, day_drop_pct=_b_day,
                                     week_drop_pct=_b_week, sma200_tol_pct=_b_sma,
                                     earnings_days=int(_b_earn), min_dte=_b_dte[0], max_dte=_b_dte[1],
                                     delta_lo=_b_delta[0], delta_hi=_b_delta[1])
        _prov = st.session_state.get("provider") or _make_provider("1d")
        st.session_state.provider = _prov
        _tks = [x.ticker for x in DEFAULT_UNIVERSE if "futures" not in x.tags and x.ticker not in _bounce.BANNED]
        for x in _bounce.BOUNCE_ETFS + _bounce.BOUNCE_FUTURES + (_bounce.BOUNCE_LEVERAGED if _b_lev else []):
            if x not in _tks:
                _tks.append(x)
        _bar = st.progress(0.0, text="Bounce scan…")
        _hits, _berr = _bounce.run_bounce(
            _prov, _tks, _bcfg,
            progress=lambda i, n, t: _bar.progress((i + 1) / n, text=f"Bounce: {t} ({i + 1}/{n})"))
        _bar.empty()
        from datetime import datetime as _dtn
        from zoneinfo import ZoneInfo as _ZI
        st.session_state.bounce = (_hits, _berr, _dtn.now(_ZI("America/New_York")), len(_tks))
        from scanner import movers as _movers
        try:
            _stk = [x.ticker for x in DEFAULT_UNIVERSE if "futures" not in x.tags and "leveraged" not in x.tags]
            st.session_state.movers = _movers.top_movers(_prov, _stk, n=5, min_avg_volume=float(_b_vol) * 1e6,
                                                         tags=_tags_all)
        except Exception as exc:
            st.session_state.movers = ([], [])
            st.caption(f"Movers unavailable: {exc}")
    if st.session_state.get("bounce"):
        _hits, _berr, _bwhen, _bn = st.session_state.bounce
        st.caption(f"🕐 {_bwhen:%m/%d %I:%M:%S %p ET} · {_bn} names checked"
                   + (f" · skipped {len(_berr)} (data errors)" if _berr else ""))
        _real = [h for h in _hits if h.status == "hit"]
        _near = [h for h in _hits if h.status == "near"]
        st.markdown(f"**{_bounce.summary(_hits)}**")
        _bnum = st.column_config.NumberColumn
        _bcols = {"Price": _bnum(format="%.2f"), "Day %": _bnum(format="%+.2f%%"), "RSI": _bnum(format="%.1f"),
                  "% vs band": _bnum(format="%+.2f%%"), "5-day %": _bnum(format="%+.1f%%"),
                  "1-mo %": _bnum(format="%+.1f%%"), "vs 200d %": _bnum(format="%+.1f%%"),
                  "Δ": _bnum(format="%.2f"), "Est. credit $": _bnum(format="$%d")}
        if _real:
            st.subheader("✅ Hits — all three triggers and the quality bar")
            st.dataframe(pd.DataFrame(_bounce.to_rows(_real)).drop(columns=["Status"]),
                         use_container_width=True, hide_index=True, column_config=_bcols)
        else:
            st.info("No clean hits right now. On a green tape that is normal — the setup fires on "
                    "the red day, and today's bounce is yesterday's hit.")
        if _b_near and _near:
            st.subheader("🟡 Near-misses — and why")
            st.dataframe(pd.DataFrame(_bounce.to_rows(_near)).drop(columns=["Trade", "Δ", "Expiry", "DTE", "Est. credit $"]),
                         use_container_width=True, hide_index=True, column_config=_bcols)
        if _hits:
            st.download_button("Download CSV", pd.DataFrame(_bounce.to_rows(_hits)).to_csv(index=False),
                               "bounce.csv", key="b_csv")
        st.caption("Earnings dates marked ? are Yahoo estimates; the broker's expected date shows "
                   "without the mark. Trades come from the live chain at 0.20-0.25 delta: a put for "
                   "bounces, a call credit spread (short call + long call ~2.5% higher) for fades — "
                   "never a naked call. '% vs band' is the lower band for bounces, the upper for fades.")
    if st.session_state.get("movers"):
        from scanner import movers as _movers
        _lo, _wi = st.session_state.movers
        st.subheader("🔄 Yesterday's biggest losers and winners")
        st.caption("Rotation list: the last completed session's five worst and five best in the liquid "
                   "universe, with today's follow-through. Losers that read 'bouncing' are the trade; "
                   "winners that read 'fading' are call-spread candidates.")
        _story = _movers.sector_story(_lo, _wi)
        if _story:
            st.markdown(f"**{_story}**")
        _m1, _m2 = st.columns(2)
        _mcols = {"Yesterday %": st.column_config.NumberColumn(format="%+.2f%%"),
                  "Today %": st.column_config.NumberColumn(format="%+.2f%%"),
                  "Yesterday close": st.column_config.NumberColumn(format="%.2f")}
        with _m1:
            st.markdown("**📉 Losers**")
            st.dataframe(pd.DataFrame(_movers.to_rows(_lo)), hide_index=True, use_container_width=True, column_config=_mcols)
        with _m2:
            st.markdown("**📈 Winners**")
            st.dataframe(pd.DataFrame(_movers.to_rows(_wi)), hide_index=True, use_container_width=True, column_config=_mcols)
    with st.expander("📟 TradingView alert mirror (1D, once per bar close)"):
        st.code(_bounce.TV_ALERT, language="javascript")

with tab_csp:
    _tab_head("csp")
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
            st.caption(f"Best strike per name and expiry, ranked by score — top {_TOP_N}. "
                       "Switch to **Table** for every column and every strike.")
            for c in dedupe_csps(result.csps)[:_TOP_N]:
                s_ = score_csp(c, _tags.get(c.ticker, frozenset()), _cfg)
                st.markdown(_card_html(c, s_, _day_flag(c.ticker) == "AT LOW"), unsafe_allow_html=True)
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
                "Gap %": result.infos[c.ticker].gap_pct if c.ticker in result.infos else None,
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
                "RSI": _num(format="%.0f"), "IVR": _num(format="%.0f"), "Gap %": _num(format="%+.1f%%"),
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
    _tab_head("ic")
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
    _tab_head("bwb")
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
    _tab_head("dip")
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
    _tab_head("scalp")
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
    _tab_head("score")
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
    _tab_head("corr")
    st.caption("PowerX-style asset correlation for YOUR book: how much your "
               "positions move together, where you're doubled up, and what "
               "would actually diversify you. Based on ~3 months of daily closes.")
    extra = st.text_input("Extra symbols to include (comma-separated, optional)", "",
                          key="corr_extra")
    if st.button("🔗 Analyze my positions", key="corr_go"):
        try:
            from scanner import correlation as corr_mod
            unders = list(_plan_ctx()["held"])
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
    _tab_head("pos")
    st.caption("Read-only, from your tastytrade account. Legs are grouped into the structure you "
               "sold — a strangle is one line with the total credit and both breakevens. "
               "'% captured' is how much of that credit you have already made.")
    if not TASTY_AVAILABLE:
        st.info("Connect tastytrade to see positions: put your API credentials in "
                "`options-scanner/.env`, then run `python -m scanner.tastytrade_check`.")
    else:
        _pc1, _pc2 = st.columns([1, 5])
        if _pc1.button("🔄 Refresh", key="pos_refresh", help="Re-pull positions, balances and quotes."):
            st.session_state.pop("plan_ctx", None)
        _ctx = _plan_ctx()
        _pc2.caption(f"Pulled {_ctx['when']:%m/%d %I:%M %p}" + (" · " + " · ".join(_ctx["errors"]) if _ctx["errors"] else ""))
        _structs = _ctx["structs"]
        if not _structs and not _ctx["rows"]:
            st.write("No open positions.")
        else:
            _sdf = pd.DataFrame([{
                " ": x.icon, "Structure": x.display, "Status": x.status.replace("_", " "),
                "Call": x.suggestion, "Qty": x.qty,
                "Credit": round(x.credit, 2), "Mark": round(x.mark_total, 2),
                "% captured": round(x.pct_of_max) if x.pct_of_max is not None else None,
                "Spot": x.spot, "BE low": x.breakeven_low, "BE high": x.breakeven_high,
                "DTE": x.dte, "P/L open": round(x.pl_open), "Held (days)": x.days_held,
                "Account": x.account,
            } for x in _structs])
            st.dataframe(_sdf, use_container_width=True, hide_index=True, column_config={
                "% captured": st.column_config.NumberColumn(format="%d%%"),
                "P/L open": st.column_config.NumberColumn(format="$%d"),
                "Spot": st.column_config.NumberColumn(format="%.2f"),
            })
            with st.expander("Every leg (raw)"):
                pos_df = pd.DataFrame(_ctx["rows"]).rename(columns={
                    "account": "Account", "display": "Contract", "symbol": "Symbol", "type": "Type",
                    "direction": "Dir", "qty": "Qty", "open_price": "Open",
                    "mark": "Mark", "pl_open": "P/L open $",
                    "pct_of_max_profit": "% of max profit",
                    "dte": "DTE", "expires": "Expires",
                    "days_held": "Held (days)"})
                cols = ["Contract", "Dir", "Qty", "Open", "Mark", "P/L open $", "% of max profit",
                        "Held (days)", "DTE", "Expires", "Type", "Account"]
                st.dataframe(pos_df[[c for c in cols if c in pos_df.columns]],
                             use_container_width=True, hide_index=True)

            # -- Roll assistant: priced on demand, never on every rerun --
            _needs = [x for x in _structs if x.status in ("tested", "breached")]
            if _needs:
                st.subheader("🔧 Roll assistant")
                st.caption("Priced when you ask (chains are slow). Strangle tested on one side → the "
                           "untested side rolled in to ≈0.25Δ. Otherwise the tested leg: same strike "
                           "out in time, or one strike further out. Credits first; a debit roll is "
                           "shown, never recommended.")
                from scanner import positions as _positions
                from scanner import roll as _roll
                from scanner.rules import futures_root as _fr
                _tp = _tasty()
                for x in _needs:
                    with st.expander(f"{x.icon} {x.display} — {x.status}"):
                        if not st.button("Price rolls", key=f"roll_{x.account}_{x.underlying}_{x.expires}"):
                            st.caption("Click to price.")
                            continue
                        try:
                            _exp = _dt.datetime.strptime(x.expires, "%m/%d/%Y").date()
                            _root = _fr(x.underlying) if x.underlying.startswith("/") else x.underlying
                            _side = _positions.untested_side(x)
                            if _side:
                                _leg = next(l for l in x.legs if l["_sign"] < 0 and l["is_put"] == (_side == "put"))
                                _r = _roll.untested_roll(_tp, _root, _exp, _side, _leg["strike"],
                                                         float(_leg["mark"]))
                                if _r is None:
                                    st.write(f"No {_side} strike closer to the money with quotes.")
                                else:
                                    _new_cr = x.credit + _r.net
                                    st.success(f"Roll the {_side.upper()} {_r.from_strike:g} → **{_r.to_strike:g}** "
                                               f"({_r.delta:.2f}Δ), same expiry, for **{_r.net_dollars * x.qty:,.0f}** "
                                               f"more credit. New total credit {_new_cr:.2f}; breakevens "
                                               f"{(x.short_put - _new_cr) if x.short_put else 0:g}–"
                                               f"{(_r.to_strike + _new_cr) if _side == 'call' else (x.short_call + _new_cr):g}.")
                            _tested_put = x.short_put is not None and x.spot is not None and x.spot <= x.short_put
                            _k = x.short_put if _tested_put else x.short_call
                            _leg = next(l for l in x.legs if l["_sign"] < 0 and l["is_put"] == _tested_put)
                            _rolls = _roll.roll_candidates(_tp, _root, _k, _tested_put, _exp,
                                                           current_mark=float(_leg["mark"]),
                                                           original_credit=x.credit)
                            if not _rolls:
                                st.write("No expiries 14–60 days further out with quotes for the tested leg.")
                            else:
                                _best = _roll.best_roll(_rolls)
                                if _best:
                                    st.info(f"Tested leg, default roll: **{_best.label}** → {_best.strike:g} "
                                            f"exp {_best.expiry:%m/%d/%Y} ({_best.dte} DTE) for a "
                                            f"**{_best.net_dollars * x.qty:,.0f} credit**; breakeven "
                                            f"{_best.new_breakeven:,.2f}.")
                                else:
                                    st.warning("Every roll of the tested leg is a debit — consider "
                                               "taking the loss instead of paying to extend it.")
                                st.dataframe(pd.DataFrame([{
                                    "Roll": r.label, "Expiry": r.expiry.strftime("%m/%d/%Y"),
                                    "DTE": r.dte, "Strike": r.strike, "New mid": r.new_mid,
                                    "Net $": round(r.net_dollars * x.qty), "Credit?": "✅" if r.is_credit else "❌ debit",
                                    "Delta": round(abs(r.delta), 2), "New breakeven": r.new_breakeven,
                                    "OI": r.open_interest,
                                } for r in _rolls]), hide_index=True, use_container_width=True)
                        except Exception as exc:
                            st.caption(f"Couldn't price rolls: {exc}")

with tab_news:
    _tab_head("news")
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
    _watch: list[str] = list(_plan_ctx()["held"])
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
