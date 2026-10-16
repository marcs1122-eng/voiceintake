"""News — the headlines that matter to a premium seller. Free RSS, no keys.

Pulls a handful of public feeds (CNBC, MarketWatch, Yahoo Finance, the
Federal Reserve) plus a Google News search per watched ticker, then scores
each headline for importance:

  * macro words (Fed, CPI, jobs, tariffs, oil …) carry the most weight
  * a headline that names one of *your* tickers — held or on today's scan —
    gets a bump, and the ticker is attached so the app can group by name
  * very fresh items get a small bump

Nothing here needs credentials. If a feed is unreachable it is skipped and
the error is reported alongside the results, never raised.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

FEEDS: dict[str, str] = {
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC Finance": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch Pulse": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
}

# Plain-English names so "Apple" tags AAPL. Kept short; tickers themselves
# also match when they appear in caps ("$NVDA", "NVDA").
NAMES: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon",
    "GOOGL": "Alphabet|Google", "META": "Meta Platforms|Facebook", "TSLA": "Tesla",
    "AMD": "AMD|Advanced Micro", "AVGO": "Broadcom", "MU": "Micron", "INTC": "Intel",
    "ORCL": "Oracle", "CRM": "Salesforce", "NFLX": "Netflix", "DIS": "Disney",
    "JPM": "JPMorgan", "BAC": "Bank of America", "GS": "Goldman", "MS": "Morgan Stanley",
    "WFC": "Wells Fargo", "C": "Citigroup", "V": "Visa", "MA": "Mastercard",
    "XOM": "Exxon", "CVX": "Chevron", "OXY": "Occidental", "COP": "ConocoPhillips",
    "KO": "Coca-Cola", "PEP": "Pepsi", "PG": "Procter", "WMT": "Walmart", "COST": "Costco",
    "TGT": "Target Corp", "HD": "Home Depot", "LOW": "Lowe's", "MCD": "McDonald's",
    "SBUX": "Starbucks", "NKE": "Nike", "TJX": "TJX|T.J. Maxx", "PM": "Philip Morris",
    "MO": "Altria", "JNJ": "Johnson & Johnson", "PFE": "Pfizer", "MRK": "Merck",
    "LLY": "Eli Lilly", "UNH": "UnitedHealth", "ABBV": "AbbVie", "BA": "Boeing",
    "CAT": "Caterpillar", "DE": "Deere", "HON": "Honeywell", "GE": "GE Aerospace",
    "UPS": "UPS", "FDX": "FedEx", "CMI": "Cummins", "RCL": "Royal Caribbean",
    "CCL": "Carnival", "MAR": "Marriott", "PLTR": "Palantir", "IONQ": "IonQ",
    "BABA": "Alibaba", "SNDK": "Sandisk", "DKS": "Dick's", "TLT": "long bond|Treasury",
    "SPY": "S&P 500", "QQQ": "Nasdaq", "IWM": "Russell 2000|small caps",
    "GLD": "gold", "SLV": "silver", "USO": "crude|oil prices", "XLE": "energy stocks",
    "EWZ": "Brazil", "FXI": "China stocks", "SMH": "chip stocks|semiconductor",
    # futures — root symbols the scanner uses
    "/ES": "S&P 500|stock futures", "/NQ": "Nasdaq", "/ZN": "Treasury|10-year|yields",
    "/ZB": "30-year|long bond", "/CL": "crude|oil prices|OPEC", "/GC": "gold",
    "/SI": "silver", "/NG": "natural gas", "/6E": "euro|ECB", "/ZS": "soybean",
    "/ZC": "corn", "/ZW": "wheat", "/RTY": "Russell 2000", "/BTC": "bitcoin",
}

# Uppercase words that look like tickers but are not, in a headline.
STOPLIST = {"AI", "IT", "US", "UK", "EU", "CEO", "CFO", "ETF", "GDP", "CPI", "FED",
            "FOMC", "SEC", "IPO", "NYSE", "PCE", "PPI", "OPEC", "TV", "UN", "NATO",
            "USA", "ALL", "ARE", "BE", "DO", "GO", "ON", "SO", "OR", "NOW", "NEW",
            "BIG", "TOP", "LIVE", "PM", "AM", "ET", "Q", "A", "I", "AN", "AT", "IN",
            "IS", "TO", "UP", "VS", "AND", "THE", "FOR", "OF", "NO", "YES", "DC",
            "CA", "NY", "LA", "SF", "PR", "HR", "IRS", "FBI", "DOJ", "FTC", "FDA",
            "EPA", "DOE", "NASA", "ISM", "RSI", "YTD", "QE", "QT", "MAG", "MO", "C",
            "V", "MA", "DE", "GE", "BA", "HD", "PG", "KO", "MS", "GS", "LOW", "COST",
            "TARGET", "TGT", "CAT", "DIS", "META", "UPS", "PM"}
# Names in the stoplist still match via NAMES (e.g. "Home Depot" → HD).

MACRO_WORDS: dict[str, int] = {
    "fomc": 4, "rate cut": 4, "rate hike": 4, "cpi": 4, "jobs report": 4,
    "payrolls": 4, "tariff": 4, "fed ": 3, "federal reserve": 3, "powell": 3,
    "interest rate": 3, "inflation": 3, "unemployment": 3, "gdp": 3, "recession": 3,
    "shutdown": 3, "opec": 3, "vix": 3, "selloff": 3, "sell-off": 3, "sells off": 3, "sell off": 3, "plunge": 3,
    "bankruptcy": 3, "crash": 3, "treasury": 2, "yield": 2, "china": 2, "oil": 2,
    "crude": 2, "gold": 2, "volatility": 2, "tumble": 2, "rally": 2, "record high": 2,
    "earnings": 2, "guidance": 2, "downgrade": 2, "acquisition": 2, "merger": 2,
    "buyout": 2, "recall": 2, "antitrust": 2, "sanction": 2, "war": 2, "missile": 2,
    "hurricane": 2, "trump": 1, "upgrade": 1, "lawsuit": 1, "ceo": 1, "strike": 1,
    "dividend": 1, "buyback": 1, "layoff": 1, "outage": 2, "hack": 2,
}

_TICKER_RE = re.compile(r"\$?\b([A-Z]{2,5})\b")
_TAGSTRIP = re.compile(r"<[^>]+>")


@dataclass
class Item:
    title: str
    link: str
    source: str
    published: dt.datetime | None
    tickers: list[str] = field(default_factory=list)
    score: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def level(self) -> str:
        return "move" if self.score >= 6 else ("note" if self.score >= 3 else "info")

    @property
    def icon(self) -> str:
        return {"move": "🔴", "note": "🟡", "info": "⚪"}[self.level]

    def age(self, now: dt.datetime | None = None) -> str:
        if self.published is None:
            return ""
        now = now or dt.datetime.now(dt.timezone.utc)
        mins = int((now - self.published).total_seconds() // 60)
        if mins < 1:
            return "now"
        if mins < 60:
            return f"{mins}m"
        if mins < 48 * 60:
            return f"{mins // 60}h"
        return f"{mins // 1440}d"


# ---------------------------------------------------------------------------
# fetching + parsing
# ---------------------------------------------------------------------------

def ticker_feed(ticker: str) -> str:
    """A Google News RSS search for one name, last three days."""
    q = ticker.lstrip("/")
    name = NAMES.get(ticker, "").split("|")[0]
    if name and name.lower() != q.lower():
        q = f'"{name}" OR {q}'
    q = f"{q} stock when:3d"
    return ("https://news.google.com/rss/search?q=" + urllib.request.quote(q)
            + "&hl=en-US&gl=US&ceid=US:en")


def _text(el, *names) -> str:
    for n in names:
        t = el.findtext(n)
        if t:
            return html.unescape(_TAGSTRIP.sub("", t)).strip()
    return ""


def _when(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def parse(raw: bytes | str, source: str) -> list[Item]:
    """RSS 2.0 or Atom → items. Google News titles end in ' - Publisher';
    that publisher becomes the source."""
    root = ET.fromstring(raw)
    A = "{http://www.w3.org/2005/Atom}"
    out: list[Item] = []
    for it in root.iter("item"):
        title = _text(it, "title")
        if not title:
            continue
        src = source
        pub = _text(it, "source")
        if pub:
            src = pub
        if " - " in title and (pub or source == "Google News"):
            title, _, tail = title.rpartition(" - ")
            src = tail.strip() or src
        out.append(Item(title, _text(it, "link", "guid"), src,
                        _when(_text(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date"))))
    for it in root.iter(A + "entry"):
        title = _text(it, A + "title")
        if not title:
            continue
        link_el = it.find(A + "link")
        link = link_el.get("href", "") if link_el is not None else ""
        out.append(Item(title, link, source, _when(_text(it, A + "published", A + "updated"))))
    return out


def fetch_one(name: str, url: str, timeout: float = 8.0) -> list[Item]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) options-scanner/1.0"})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return parse(raw, name)


def fetch_all(feeds: dict[str, str], watch: list[str] = (), timeout: float = 8.0,
              workers: int = 6, max_ticker_feeds: int = 10) -> tuple[list[Item], dict[str, str]]:
    """Every feed plus one Google News search per watched ticker, in parallel.
    Returns (items, errors-by-feed)."""
    jobs = dict(feeds)
    for tk in list(watch)[:max_ticker_feeds]:
        jobs[f"Google News · {tk}"] = ticker_feed(tk)
    items: list[Item] = []
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, n, u, timeout): n for n, u in jobs.items()}
        for f in as_completed(futs):
            n = futs[f]
            try:
                got = f.result()
                for it in got:
                    if n.startswith("Google News") and it.source == n:
                        it.source = "Google News"
                items += got
            except Exception as exc:
                errors[n] = str(exc)[:120]
    return rank(items, watch), errors


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


def tag_tickers(title: str, watch: list[str] = ()) -> list[str]:
    """Tickers a headline is about: caps symbols (minus the stoplist) plus
    plain-English names from NAMES. Watched names are checked by name too."""
    found: list[str] = []
    for m in _TICKER_RE.finditer(title):
        sym = m.group(1)
        if sym in STOPLIST and not title[m.start()] == "$":
            continue
        if sym in NAMES or sym in watch or title[m.start()] == "$":
            found.append(sym)
    low = title.lower()
    for tk, names in NAMES.items():
        for nm in names.split("|"):
            if nm.lower() in low and tk not in found:
                found.append(tk)
                break
    return found


def score(item: Item, watch: list[str] = (), now: dt.datetime | None = None) -> Item:
    low = " " + item.title.lower() + " "
    s, tags = 0, []
    for w, pts in MACRO_WORDS.items():
        if w in low:
            s += pts
            tags.append(w.strip())
    s = min(s, 8)
    item.tickers = tag_tickers(item.title, watch)
    if any(t in watch for t in item.tickers):
        s += 4
        tags.append("your name")
    elif item.tickers:
        s += 1
    if item.published is not None:
        now = now or dt.datetime.now(dt.timezone.utc)
        if (now - item.published) <= dt.timedelta(hours=2):
            s += 1
    item.score, item.tags = s, tags
    return item


def rank(items: list[Item], watch: list[str] = (), now: dt.datetime | None = None) -> list[Item]:
    """Score, drop duplicates (same headline from two feeds), newest-important first."""
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        k = _norm(it.title)[:80]
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(score(it, watch, now))
    far = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    out.sort(key=lambda i: (-i.score, -(i.published or far).timestamp()))
    return out


def split(items: list[Item], watch: list[str] = ()) -> dict[str, list[Item]]:
    """Three buckets for the tab: market-moving, your names, everything else."""
    move = [i for i in items if i.level == "move"]
    mine = [i for i in items if any(t in watch for t in i.tickers) and i not in move]
    rest = [i for i in items if i not in move and i not in mine]
    return {"move": move, "mine": mine, "rest": rest}
