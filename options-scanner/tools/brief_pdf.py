#!/usr/bin/env python3
"""Render a trading brief as a one-page, printable PDF (and PNG).

The scheduled briefs are useless if they only live in chat — Mac prints one
every morning and works off the paper. This turns a small JSON file into a
Letter-size sheet with the same typography as the Core 20 and Futures cards,
so they all sit in the same binder.

    python3 tools/brief_pdf.py brief.json -o out/

Produces out/<slug>.pdf and out/<slug>.png (276 DPI — print the PNG when a
PDF reader isn't handy; every device prints an image).

Input JSON — every section optional except title/date:

    {
      "title":  "Options Morning Brief",
      "date":   "Wednesday 09/02/2026",
      "pulled": "8:46am ET",
      "lede":   "one italic sentence under the title",
      "posture": {
        "note": "one line on what the tape means",
        "rows": [{"sym":"/ES","last":"7,646.75","chg":"+0.05%",
                  "rsi":"47.3","read":"Neutral"}]
      },
      "candidates": [
        {"ticker":"TJX","spot":"133.27","rsi":"21.1",
         "signals":"4th day oversold · band 127.37",
         "zone":"125P area","note":"why now","size":"3 contracts max"}
      ],
      "loud":   "quality names at RSI<=30, one line",
      "avoid":  [{"ticker":"PCG","note":"why to skip"}],
      "todo":   ["housekeeping line", "another"],
      "footer": "closing reminder"
    }

Needs: pip install playwright   (Chromium is found automatically)
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


def build_html(b: dict, fonts: str) -> str:
    posture = b.get("posture") or {}
    rows = posture.get("rows") or []
    cands = b.get("candidates") or []
    avoid = b.get("avoid") or []
    todo = b.get("todo") or []

    posture_html = ""
    if rows:
        cells = "".join(
            f'<div class="pcell"><span class="psym">{e(r.get("sym"))}</span>'
            f'<span class="plast">{e(r.get("last"))}</span>'
            f'<span class="pchg {"dn" if str(r.get("chg","")).startswith("-") else "up"}">'
            f'{e(r.get("chg"))}</span>'
            f'<span class="prsi">RSI {e(r.get("rsi"))}</span>'
            f'<span class="pread">{e(r.get("read"))}</span></div>'
            for r in rows)
        note = (f'<p class="pnote">{e(posture.get("note"))}</p>'
                if posture.get("note") else "")
        posture_html = (f'<section class="posture"><span class="k">Market posture</span>'
                        f'<div class="pgrid">{cells}</div>{note}</section>')

    cand_html = ""
    if cands:
        items = []
        for i, c in enumerate(cands, 1):
            bits = []
            if c.get("signals"):
                bits.append(f'<span class="csig">{e(c["signals"])}</span>')
            if c.get("note"):
                bits.append(f'<span class="cnote">{e(c["note"])}</span>')
            if c.get("size"):
                bits.append(f'<span class="csize">{e(c["size"])}</span>')
            items.append(
                f'<li><div class="chead"><span class="cn">{i}</span>'
                f'<span class="ctkr">{e(c.get("ticker"))}</span>'
                f'<span class="cspot">{e(c.get("spot"))}</span>'
                f'<span class="crsi">RSI {e(c.get("rsi"))}</span>'
                f'<span class="czone">{e(c.get("zone"))}</span></div>'
                f'<div class="cbody">{" · ".join(bits)}</div></li>')
        cand_html = ('<section class="block"><h2>Put-sale candidates</h2>'
                     f'<ol class="cands">{"".join(items)}</ol></section>')

    loud_html = (f'<section class="loud"><span class="k">Quality at RSI 30 or under</span>'
                 f'<p>{e(b["loud"])}</p></section>') if b.get("loud") else ""

    avoid_html = ""
    if avoid:
        lis = "".join(f'<li><b>{e(a.get("ticker"))}</b> — {e(a.get("note"))}</li>'
                      for a in avoid)
        avoid_html = ('<section class="panel avoid"><h3>Do not sell puts here</h3>'
                      f'<ul>{lis}</ul></section>')

    todo_html = ""
    if todo:
        lis = "".join(f"<li>{e(t)}</li>" for t in todo)
        todo_html = ('<section class="panel todo"><h3>Your rules, today</h3>'
                     f'<ul>{lis}</ul></section>')

    panels = (f'<div class="panels">{avoid_html}{todo_html}</div>'
              if (avoid_html or todo_html) else "")
    footer = f'<p class="footer">{e(b["footer"])}</p>' if b.get("footer") else ""
    lede = f'<p class="sub">{e(b["lede"])}</p>' if b.get("lede") else ""
    pulled = (f'PULLED <b>{e(b["pulled"])}</b><br>' if b.get("pulled") else "")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{e(b.get('title','Brief'))}</title>
<style>
{fonts}
:root{{
  --paper:#fbfbfa;--sheet:#fff;--ink:#17191c;--ink-2:#565b60;--ink-3:#878d93;
  --rule:#d8dbd8;--rule-2:#eceeeb;--accent:#2f5573;--accent-wash:#eaf0f5;
  --good:#2d6a4a;--warn:#9a5b28;--band:#f1f3f5;
}}
*{{box-sizing:border-box}}
html,body{{background:#fff}}
body{{color:var(--ink);font-family:"Archivo","Helvetica Neue",Arial,sans-serif;
  font-size:10.4pt;line-height:1.45;margin:0;-webkit-font-smoothing:antialiased}}
.sheet{{max-width:none;padding:0}}

.masthead{{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;
  border-bottom:2px solid var(--ink);padding-bottom:8px}}
.eyebrow{{font-size:8.5px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 3px}}
h1{{font-size:22pt;font-weight:800;letter-spacing:-.024em;line-height:1;margin:0;
  text-wrap:balance}}
.sub{{font-family:"Newsreader",Georgia,serif;font-size:11.5px;font-style:italic;
  color:var(--ink-2);margin:4px 0 0;max-width:42ch}}
.stamp{{text-align:right;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:8.6px;line-height:1.55;color:var(--ink-3);white-space:nowrap;
  font-variant-numeric:tabular-nums}}
.stamp b{{color:var(--ink-2);font-weight:500}}

.k{{font-size:7.6px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);display:block;margin-bottom:4px}}

.posture{{background:var(--accent-wash);border-bottom:1px solid var(--rule);
  padding:9px 13px 10px}}
.pgrid{{display:grid;grid-template-columns:repeat(6,1fr);gap:0 10px}}
.pcell{{display:flex;flex-direction:column;gap:0;
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.psym{{font-size:11px;font-weight:600;color:var(--accent)}}
.plast{{font-size:11px;color:var(--ink)}}
.pchg{{font-size:9.4px}}
.pchg.up{{color:var(--good)}} .pchg.dn{{color:var(--warn)}}
.prsi,.pread{{font-size:9px;color:var(--ink-3)}}
.pnote{{font-family:"Newsreader",Georgia,serif;font-size:11.5px;color:var(--ink);
  margin:8px 0 0;line-height:1.45}}

.block{{margin-top:11px}}
h2{{font-size:8.4px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 5px;padding-bottom:4px;border-bottom:1px solid var(--rule)}}
ol.cands{{list-style:none;margin:0;padding:0}}
ol.cands li{{padding:5px 0;border-bottom:1px solid var(--rule-2)}}
.chead{{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}}
.cn{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:9.4px;
  font-weight:600;color:var(--ink-3);width:1.1em}}
.ctkr{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px;
  font-weight:600;color:var(--accent);letter-spacing:-.01em}}
.cspot,.crsi{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;
  color:var(--ink);font-variant-numeric:tabular-nums}}
.crsi{{color:var(--ink-2)}}
.czone{{margin-left:auto;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:11px;font-weight:600;color:var(--good);white-space:nowrap}}
.cbody{{font-family:"Newsreader",Georgia,serif;font-size:11px;color:var(--ink-2);
  margin:1px 0 0 calc(1.1em + 9px);line-height:1.4}}
.csig{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:9.4px;
  color:var(--ink-3)}}
.csize{{color:var(--warn)}}

.loud{{margin-top:10px;padding:8px 12px;background:var(--band);
  border-left:3px solid var(--good)}}
.loud p{{margin:0;font-family:"Newsreader",Georgia,serif;font-size:11.5px;
  line-height:1.45}}

.panels{{display:grid;grid-template-columns:1fr 1fr;gap:0 24px;margin-top:12px;
  padding-top:10px;border-top:2px solid var(--ink)}}
.panel h3{{font-size:7.6px;font-weight:600;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink-3);margin:0 0 4px}}
.panel ul{{margin:0;padding-left:15px}}
.panel li{{font-family:"Newsreader",Georgia,serif;font-size:11px;line-height:1.42;
  margin-bottom:4px}}
.avoid li b{{color:var(--warn)}}
.todo li b{{color:var(--accent)}}

.footer{{margin-top:10px;padding-top:7px;border-top:1px solid var(--rule-2);
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:8.4px;
  line-height:1.5;color:var(--ink-3)}}

@page{{size:letter portrait;margin:0.42in}}
@media print{{*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  ol.cands li,.panels,.posture{{break-inside:avoid;page-break-inside:avoid}}}}
</style></head><body><div class="sheet">
<header class="masthead">
  <div>
    <p class="eyebrow">{e(b.get('eyebrow','Not financial advice · confirm live premiums before entering'))}</p>
    <h1>{e(b.get('title','Brief'))}</h1>
    {lede}
  </div>
  <div class="stamp">{pulled}<b>{e(b.get('date',''))}</b><br>{e(b.get('source','TradingView'))}</div>
</header>
{posture_html}{cand_html}{loud_html}{panels}{footer}
</div></body></html>"""


# ---------------------------------------------------------------------------

def render(brief: dict, outdir: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    import asyncio
    from playwright.async_api import async_playwright

    outdir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-",
                  f"{brief.get('title','brief')} {brief.get('date','')}".lower()).strip("-")
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
    ap = argparse.ArgumentParser(description="Render a trading brief to a printable PDF.")
    ap.add_argument("brief", help="JSON file (or - for stdin)")
    ap.add_argument("-o", "--outdir", default="out")
    args = ap.parse_args()
    raw = sys.stdin.read() if args.brief == "-" else pathlib.Path(args.brief).read_text()
    pdf, png = render(json.loads(raw), pathlib.Path(args.outdir))
    print(f"{pdf}\n{png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
