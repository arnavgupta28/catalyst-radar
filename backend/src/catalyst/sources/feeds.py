"""Small parsers: RSS, NSE announcements JSON, SEC EDGAR submissions, TinyFish Search hits."""

from __future__ import annotations

import json
import warnings
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from catalyst.providers.tinyfish import SearchHit
from catalyst.schemas import RawItem

IST = ZoneInfo("Asia/Kolkata")
# We parse RSS with the stdlib-backed html.parser on purpose (no lxml dependency; tolerant of broken feeds).
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def parse_rss(xml: str, source_id: str, outlet: str | None = None) -> list[RawItem]:
    soup = BeautifulSoup(xml, "html.parser")
    channel = soup.find("title")
    outlet = outlet or (channel.get_text(strip=True) if channel else None)
    out = []
    for item in soup.find_all("item"):
        title = item.find("title")
        url = _rss_link(item)
        if not title or not url:
            continue
        desc = item.find("description")
        pub = item.find("pubdate")
        published = None
        if pub:
            try:
                published = parsedate_to_datetime(pub.get_text(strip=True))
            except (TypeError, ValueError):
                published = None
        summary = BeautifulSoup(desc.get_text(), "html.parser").get_text(" ", strip=True) if desc else ""
        out.append(
            RawItem(
                source_id=source_id,
                url=url,
                title=title.get_text(" ", strip=True),
                summary=summary[:500],
                published_at=published,
                outlet=outlet,
            )
        )
    return out


def _rss_link(item: Tag) -> str:
    """html.parser treats <link> as void, so the URL ends up as the following text node."""
    link = item.find("link")
    if link is not None:
        text = link.get_text(strip=True)
        if text:
            return text
        sib = link.next_sibling
        if isinstance(sib, str) and sib.strip().startswith("http"):
            return sib.strip()
    guid = item.find("guid")
    if guid is not None and guid.get_text(strip=True).startswith("http"):
        return guid.get_text(strip=True)
    return ""


def parse_nse_announcements(text: str, source_id: str, symbol: str | None = None) -> list[RawItem]:
    rows = json.loads(text)
    if isinstance(rows, dict):
        rows = rows.get("data", [])
    out = []
    for r in rows:
        published = None
        if r.get("an_dt"):
            try:
                published = datetime.strptime(r["an_dt"], "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
            except ValueError:
                published = None
        name = r.get("sm_name") or r.get("symbol") or symbol or ""
        out.append(
            RawItem(
                source_id=source_id,
                url=r.get("attchmntFile")
                or "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
                title=f"{name}: {r.get('desc', 'Announcement')}",
                summary=r.get("attchmntText", "") or "",
                published_at=published,
                outlet="NSE",
                company_hint=r.get("symbol") or symbol,
                payload={"seq_id": r.get("seq_id"), "industry": r.get("smIndustry")},
            )
        )
    return out


_SEC_FORMS = {"8-K", "6-K", "10-Q", "10-K", "20-F", "S-1", "SC 13D", "SC 13G"}


def parse_sec_submissions(text: str, source_id: str, symbol: str | None = None, limit: int = 20) -> list[RawItem]:
    data = json.loads(text)
    recent = data.get("filings", {}).get("recent", {})
    cik = str(data.get("cik", "")).lstrip("0")
    name = data.get("name") or symbol or ""
    symbol = (data.get("tickers") or [symbol])[0]  # the filer's own ticker beats the listing we asked about
    out = []
    forms = recent.get("form", [])
    for i, form in enumerate(forms):
        if form not in _SEC_FORMS:
            continue
        acc = recent["accessionNumber"][i]
        doc = recent.get("primaryDocument", [""] * len(forms))[i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
        desc = (recent.get("primaryDocDescription") or [""] * len(forms))[i] or form
        items = (recent.get("items") or [""] * len(forms))[i]
        published = None
        try:
            published = datetime.fromisoformat(recent["acceptanceDateTime"][i].replace("Z", "+00:00"))
        except (KeyError, ValueError, IndexError):
            published = None
        out.append(
            RawItem(
                source_id=source_id,
                url=url,
                title=f"{name}: {form} – {desc}",
                summary=f"Items: {items}" if items else "",
                published_at=published,
                outlet="SEC EDGAR",
                company_hint=symbol,
                payload={"form": form, "items": items},
            )
        )
        if len(out) >= limit:
            break
    return out


def hits_to_items(hits: list[SearchHit], source_id: str, company_hint: str | None) -> list[RawItem]:
    out = []
    for h in hits:
        published = None
        if h.published:
            try:
                published = datetime.fromisoformat(h.published.replace("Z", "+00:00"))
            except ValueError:
                published = None
        out.append(
            RawItem(
                source_id=source_id,
                url=h.url,
                title=h.title,
                summary=h.snippet,
                outlet=h.site_name or None,
                published_at=published,
                company_hint=company_hint,
                payload={"position": h.position},
            )
        )
    return out
