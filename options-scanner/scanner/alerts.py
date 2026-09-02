"""Alerts — the things a premium seller should be told about right now.

Built from whatever is on hand: the last scan, live positions, the
rulebook checks. Three levels:

  act    — do something today (a position at its profit target, a tested
           strike, a rule breached, earnings on a held name this week)
  watch  — a setup worth looking at (quality name washed out, at the day's
           low, through its lower band; a rule near its limit)
  info   — housekeeping

The scheduled routines send these by email; the app lists them at the top
of the Trade Plan and can email them itself when SMTP is configured
(ALERT_SMTP_HOST / ALERT_SMTP_PORT / ALERT_SMTP_USER / ALERT_SMTP_PASS /
ALERT_TO).
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass

LEVEL_ORDER = {"act": 0, "watch": 1, "info": 2}


@dataclass
class Alert:
    level: str          # act | watch | info
    ticker: str
    text: str

    @property
    def icon(self) -> str:
        return {"act": "🔴", "watch": "🟡", "info": "⚪"}[self.level]


def build_alerts(result=None, tags: dict | None = None, positions: list[dict] = (),
                 checks: list = (), today: dt.date | None = None) -> list[Alert]:
    tags = tags or {}
    today = today or dt.date.today()
    out: list[Alert] = []

    # -- positions: the ladder and the 21-DTE window --
    for r in positions:
        s = str(r.get("suggestion", ""))
        disp = r.get("display") or r.get("symbol", "")
        if "CLOSE" in s or "TESTED" in s or "BREACHED" in s:
            out.append(Alert("act", r.get("underlying", ""), f"{disp}: {s}"))
        elif "ROLL FORWARD" in s or "DTE" in s:
            out.append(Alert("watch", r.get("underlying", ""), f"{disp}: {s}"))

    # -- rulebook --
    for c in checks:
        st = getattr(c, "status", "")
        if st == "breach":
            out.append(Alert("act", "", f"Rule breached — {c.name}: {c.detail}"))
        elif st == "warn":
            out.append(Alert("watch", "", f"Near a limit — {c.name}: {c.detail}"))

    # -- scan: quality names washed out, at the low, through the band --
    held = {r.get("underlying") for r in positions}
    if result is not None:
        for tk, info in result.infos.items():
            t = tags.get(tk, frozenset())
            quality = bool({"blue-chip", "etf"} & t)
            if info.next_earnings and tk in held and 0 <= (info.next_earnings - today).days <= 7:
                out.append(Alert("act", tk, f"{tk} reports {info.next_earnings:%m/%d} — "
                                            "you hold it; no short strike through the print"))
            if not quality:
                continue
            bits = []
            if info.rsi_14 <= 30:
                bits.append(f"RSI {info.rsi_14:.0f}")
            if info.boll_lower and info.spot <= info.boll_lower:
                bits.append("through its lower band")
            if info.at_day_low:
                bits.append("at the low of day")
            if bits:
                out.append(Alert("watch", tk, f"{tk} {info.spot:,.2f} — " + ", ".join(bits)))

    out.sort(key=lambda a: (LEVEL_ORDER[a.level], a.ticker))
    return out


def format_text(alerts: list[Alert], when: str = "") -> str:
    if not alerts:
        return "Nothing needs action."
    lines = [f"Scanner alerts {when}".strip(), ""]
    for lvl, title in (("act", "ACT TODAY"), ("watch", "WATCH"), ("info", "INFO")):
        group = [a for a in alerts if a.level == lvl]
        if group:
            lines.append(title)
            lines += [f"  - {a.text}" for a in group]
            lines.append("")
    return "\n".join(lines).rstrip()


def smtp_configured() -> bool:
    return bool(os.environ.get("ALERT_SMTP_HOST") and os.environ.get("ALERT_TO"))


def send_email(alerts: list[Alert], subject: str = "Scanner alerts") -> str:
    """Send via SMTP from environment settings. Returns a status string;
    never raises (the app shows the string)."""
    import smtplib
    from email.message import EmailMessage

    if not smtp_configured():
        return "SMTP not configured (set ALERT_SMTP_HOST, ALERT_SMTP_PORT, ALERT_SMTP_USER, ALERT_SMTP_PASS, ALERT_TO)"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("ALERT_SMTP_USER") or os.environ["ALERT_TO"]
    msg["To"] = os.environ["ALERT_TO"]
    msg.set_content(format_text(alerts, dt.datetime.now().strftime("%m/%d %I:%M %p")))
    try:
        with smtplib.SMTP(os.environ["ALERT_SMTP_HOST"], int(os.environ.get("ALERT_SMTP_PORT", "587")), timeout=20) as s:
            s.starttls()
            if os.environ.get("ALERT_SMTP_USER"):
                s.login(os.environ["ALERT_SMTP_USER"], os.environ.get("ALERT_SMTP_PASS", ""))
            s.send_message(msg)
        return f"Sent {len(alerts)} alert(s) to {os.environ['ALERT_TO']}"
    except Exception as exc:
        return f"Email failed: {exc}"
