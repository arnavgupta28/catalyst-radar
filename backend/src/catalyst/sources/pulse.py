"""Zerodha Pulse: ~170 stories from the last 24 h across major Indian business outlets.

Structure (checked 7 Nov 2026):
  li.box.item#item-<n>
    h2.title > a[href][data-id]   headline + original article URL
    div.desc                      summary
    span.date[title]              "06:33 PM, 07 Nov 2026" (IST)
    span.feed                     "— NDTV Business"
    ul.similar > li               same story from other outlets (a.title2, span.date, span.feed)
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from catalyst.schemas import RawItem

IST = ZoneInfo("Asia/Kolkata")


def _parse_time(title: str | None) -> datetime | None:
    if not title:
        return None
    try:
        return datetime.strptime(title.strip(), "%I:%M %p, %d %b %Y").replace(tzinfo=IST)
    except ValueError:
        return None


def _text(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _outlet(node: Tag | None) -> str | None:
    t = _text(node).lstrip("—-– ").strip()
    return t or None


def parse_pulse(html: str, source_id: str = "pulse") -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[RawItem] = []
    for li in soup.select("li.box.item"):
        link = li.select_one("h2.title > a")
        if not link or not link.get("href"):
            continue
        similar = li.select("ul.similar > li")
        related_urls = [str(a["href"]) for s in similar if (a := s.select_one("a")) and a.get("href")]
        related_outlets = sorted({o for s in similar if (o := _outlet(s.select_one("span.feed")))})
        items.append(
            RawItem(
                source_id=source_id,
                url=str(link["href"]).split("#")[0],
                title=_text(link),
                summary=_text(li.select_one("div.desc")),
                published_at=_parse_time(str(li.select_one("span.date")["title"]))  # type: ignore[index]
                if li.select_one("span.date[title]")
                else None,
                outlet=_outlet(li.find("span", class_="feed", recursive=False)),
                related_count=len(similar),
                related_urls=related_urls,
                payload={
                    "pulse_id": str(link.get("data-id") or li.get("id", "")).replace("item-", ""),
                    "related_outlets": related_outlets,
                },
            )
        )
    return items
