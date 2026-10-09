#!/usr/bin/env python3
"""Render the morning brief as a BIG-PRINT one-page sheet.

Mac reads this on paper at 8:45am, in a hurry. The old layout fit five
sections on a page at 9-11px and he told us it was too much small print to
follow. This one carries less and prints it larger: nothing under 12pt, the
tickers at 24pt, and a hard cap of three trades.

    python3 tools/brief_simple.py brief.json -o out/

Input JSON:

    {
      "date":     "Monday 09/14/2026",
      "headline": "the ONE thing that matters today, one sentence",
      "trades": [                       # 3 max; fewer is better
        {"ticker":"USFD", "action":"Sell the Oct 16 90 put",
         "size":"5 contracts", "why":"RSI 28, under its band, week -8.7%"}
      ],
      "positions": [                    # what he already owns
        {"ticker":"/CL", "status":"AT RISK",   # AT RISK | WATCH | OK
         "action":"Close or roll the 108.5 call. Expires Thursday."}
      ],
      "market": ["one short line", "another", "a third"],   # 3 max
      "skip":   "one line naming what not to touch today",
      "note":   "optional single caveat line at the foot"
    }

Needs: pip install playwright
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import pathlib
import re
import sys
import urllib.request

FONT_CSS_URL = ("https://fonts.googleapis.com/css2"
                "?family=Archivo:wght@400;500;600;800"
                "&family=IBM+Plex+Mono:wght@400;500;600"
                "&family=Newsreader:ital,wght@0,400;1,400&display=swap")
CACHE = pathlib.Path.home() / ".cache" / "brief-pdf"


# ---------------------------------------------------------------------------
# Fonts: fetch once, inline as data URIs. Chromium in a sandbox often can't
# reach fonts.gstatic.com itself, so we fetch here and embed.
# ---------------------------------------------------------------------------

def inline_fonts() -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "fonts.css"
    if cached.exists():
        return cached.read_text()

    def get(url: str) -> bytes:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120 Safari/537.36"})
        return urllib.request.urlopen(req, timeout=60).read()

    try:
        css = get(FONT_CSS_URL).decode()
    except Exception as exc:                       # offline → fallback stacks
        print(f"  fonts unavailable ({exc}); using system fallbacks", file=sys.stderr)
        return ""

    faces, seen = [], {}
    for subset, face in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{.*?\})",
                                   css, re.S):
        if subset not in ("latin", "latin-ext"):
            continue
        m = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", face)
        if not m:
            continue
        url = m.group(1)
        if url not in seen:
            try:
                seen[url] = ("data:font/woff2;base64,"
                             + base64.b64encode(get(url)).decode())
            except Exception:
                continue
        face = face.replace(url, seen[url])
        faces.append(re.sub(r"\s*unicode-range:[^;]+;", "", face))

    out = "\n".join(faces)
    if out:
        cached.write_text(out)
    return out


def find_chromium() -> str | None:
    for base in (pathlib.Path("/opt/pw-browsers"),
                 pathlib.Path.home() / ".cache" / "ms-playwright"):
        if not base.exists():
            continue
        for d in sorted(base.glob("chromium-*"), reverse=True):
            exe = d / "chrome-linux" / "chrome"
            if exe.exists():
                return str(exe)
    return None


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def e(x) -> str:
    return html.escape(str(x if x is not None else ""))




STATUS_CLASS = {"AT RISK": "risk", "WATCH": "watch", "OK": "ok"}


def build_html(b: dict, fonts: str) -> str:
    e = html.escape

    trades = ""
    for i, t in enumerate(b.get("trades", [])[:3], 1):
        why = f'<div class="why">{e(t["why"])}</div>' if t.get("why") else ""
        size = f'<span class="size">{e(t["size"])}</span>' if t.get("size") else ""
        trades += (
            f'<li><div class="row"><span class="num">{i}</span>'
            f'<span class="tkr">{e(t.get("ticker",""))}</span>'
            f'<span class="act">{e(t.get("action",""))}</span>{size}</div>{why}</li>')
    trades = (f'<section><h2>Do this</h2><ol class="trades">{trades}</ol></section>'
              if trades else
              '<section><h2>Do this</h2>'
              '<p class="none">Nothing qualified today. Sit out.</p></section>')

    pos = ""
    for p in b.get("positions", []):
        s = p.get("status", "WATCH").upper()
        pos += (f'<li><span class="badge {STATUS_CLASS.get(s,"watch")}">{e(s)}</span>'
                f'<span class="ptkr">{e(p.get("ticker",""))}</span>'
                f'<span class="pact">{e(p.get("action",""))}</span></li>')
    pos = (f'<section><h2>Your positions</h2><ul class="pos">{pos}</ul></section>'
           if pos else "")

    mkt = "".join(f"<li>{e(m)}</li>" for m in b.get("market", [])[:3])
    mkt = f'<section><h2>Market</h2><ul class="mkt">{mkt}</ul></section>' if mkt else ""

    skip = (f'<section class="skip"><h2>Skip</h2><p>{e(b["skip"])}</p></section>'
            if b.get("skip") else "")
    note = f'<p class="note">{e(b["note"])}</p>' if b.get("note") else ""
    head = (f'<p class="headline">{e(b["headline"])}</p>' if b.get("headline") else "")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Morning Brief</title>
<style>
{fonts}
:root{{--ink:#15171a;--ink-2:#4a5057;--ink-3:#7c838a;--rule:#d5d9dc;
  --risk:#b03a2e;--watch:#9a6b28;--ok:#2d6a4a;--accent:#22405c;--wash:#f3f5f7}}
*{{box-sizing:border-box}}
html,body{{background:#fff;margin:0}}
body{{font-family:"Archivo",system-ui,sans-serif;color:var(--ink);
  font-size:13pt;line-height:1.5;-webkit-font-smoothing:antialiased;padding:0}}
.sheet{{max-width:7.1in;margin:0 auto}}
header{{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:3px solid var(--ink);padding-bottom:8px;margin-bottom:16px}}
h1{{font-size:27pt;font-weight:800;letter-spacing:-.02em;margin:0;line-height:1}}
.date{{font-size:12pt;font-weight:600;color:var(--ink-2);white-space:nowrap}}
.headline{{font-size:15pt;line-height:1.38;font-weight:600;margin:0 0 20px;
  padding:12px 14px;background:var(--wash);border-left:5px solid var(--accent)}}
section{{margin:0 0 18px}}
h2{{font-size:10pt;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 8px;padding-bottom:4px;border-bottom:1px solid var(--rule)}}
ol.trades{{list-style:none;margin:0;padding:0}}
ol.trades li{{padding:9px 0;border-bottom:1px solid #eef0f1}}
ol.trades li:last-child{{border-bottom:0}}
.row{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.num{{font-size:13pt;font-weight:800;color:var(--ink-3);min-width:16px}}
.tkr{{font-family:"IBM Plex Mono",monospace;font-size:24pt;font-weight:600;
  letter-spacing:-.01em;line-height:1}}
.act{{font-size:14pt;font-weight:600;color:var(--accent)}}
.size{{font-size:12pt;font-weight:600;color:var(--ink-2);white-space:nowrap}}
.why{{font-size:12pt;color:var(--ink-2);margin:3px 0 0 26px}}
.none{{font-size:14pt;font-weight:600;color:var(--ink-2);margin:6px 0}}
ul.pos{{list-style:none;margin:0;padding:0}}
ul.pos li{{display:flex;align-items:baseline;gap:10px;padding:7px 0;
  border-bottom:1px solid #eef0f1}}
ul.pos li:last-child{{border-bottom:0}}
.badge{{font-size:9pt;font-weight:700;letter-spacing:.08em;padding:3px 7px;
  border-radius:3px;color:#fff;white-space:nowrap;min-width:64px;text-align:center}}
.badge.risk{{background:var(--risk)}}
.badge.watch{{background:var(--watch)}}
.badge.ok{{background:var(--ok)}}
.ptkr{{font-family:"IBM Plex Mono",monospace;font-size:14pt;font-weight:600;
  min-width:62px}}
.pact{{font-size:12.5pt;color:var(--ink);flex:1}}
ul.mkt{{list-style:none;margin:0;padding:0}}
ul.mkt li{{font-size:12.5pt;color:var(--ink-2);padding:3px 0}}
ul.mkt li:before{{content:"— ";color:var(--ink-3)}}
.skip p{{font-size:12.5pt;color:var(--ink-2);margin:0}}
.note{{font-size:10.5pt;color:var(--ink-3);border-top:1px solid var(--rule);
  padding-top:8px;margin:18px 0 0}}
@page{{size:letter portrait;margin:0.5in}}
@media print{{body{{padding:0}} section,ol.trades li{{break-inside:avoid}}}}
</style></head><body><div class="sheet">
<header><h1>Morning Brief</h1><span class="date">{e(b.get('date',''))}</span></header>
{head}{trades}{pos}{mkt}{skip}{note}
</div></body></html>"""


def slugify(b: dict) -> str:
    s = "morning-brief-" + str(b.get("date", "")).lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-") or "brief"


def render(brief: dict, outdir: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    import asyncio
    from playwright.async_api import async_playwright

    outdir.mkdir(parents=True, exist_ok=True)
    slug = slugify(brief)
    doc = outdir / f"{slug}.html"
    doc.write_text(build_html(brief, inline_fonts()))
    pdf, png = outdir / f"{slug}.pdf", outdir / f"{slug}.png"
    exe = find_chromium()

    async def go():
        async with async_playwright() as p:
            kw = {"executable_path": exe} if exe else {}
            br = await p.chromium.launch(**kw)
            pg = await br.new_page(viewport={"width": 736, "height": 975})
            await pg.emulate_media(color_scheme="light", media="print")
            await pg.goto("file://" + str(doc.resolve()))
            try:
                await pg.evaluate("document.fonts.ready")
            except Exception:
                pass
            h = await pg.evaluate(
                "document.querySelector('.sheet').getBoundingClientRect().height")
            scale = min(1.0, 975.0 / h) if h else 1.0
            if scale < 0.72:
                print(f"  note: content is long ({h:.0f}px) — will run to 2 pages",
                      file=sys.stderr)
                scale = 1.0
            await pg.pdf(path=str(pdf), format="Letter", print_background=True,
                         scale=round(scale, 3),
                         margin={"top": "0.42in", "bottom": "0.42in",
                                 "left": "0.42in", "right": "0.42in"})
            await br.close()
            # Second pass at 3x for the printable image. The print stylesheet
            # zeroes body padding (the @page margin supplies it), so the PNG
            # needs that margin painted back on or the right-hand strike-zone
            # column runs off the paper edge. Short viewport + full_page lets
            # the capture shrink to the content instead of trailing white.
            br = await p.chromium.launch(**kw)
            pg = await br.new_page(viewport={"width": 736, "height": 400},
                                   device_scale_factor=3)
            await pg.emulate_media(color_scheme="light", media="print")
            await pg.goto("file://" + str(doc.resolve()))
            try:
                await pg.evaluate("document.fonts.ready")
            except Exception:
                pass
            await pg.evaluate(
                "document.body.style.padding='40px';"
                "document.body.style.background='#fff';"
                "document.documentElement.style.background='#fff'")
            await pg.screenshot(path=str(png), full_page=True)
            await br.close()

    asyncio.run(go())
    return pdf, png


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the big-print morning brief.")
    ap.add_argument("brief", help="JSON file (or - for stdin)")
    ap.add_argument("-o", "--outdir", default="out")
    args = ap.parse_args()
    raw = sys.stdin.read() if args.brief == "-" else pathlib.Path(args.brief).read_text()
    pdf, png = render(json.loads(raw), pathlib.Path(args.outdir))
    print(f"{pdf}\n{png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
