"""Moneycontrol: news lists (HTML) + market-data pages (embedded __NEXT_DATA__ JSON).

We parse only public pages. The internal api.moneycontrol.com endpoints referenced in the page
config are deliberately NOT called.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from catalyst.schemas import RawItem

IST = ZoneInfo("Asia/Kolkata")
_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def next_data(html: str) -> dict[str, Any]:
    m = _NEXT.search(html)
    if not m:
        raise ValueError("no __NEXT_DATA__ block (page layout changed?)")
    return json.loads(m.group(1))["props"]["pageProps"]


# ------------------------------------------------------------------ news list
def parse_news_list(html: str, source_id: str, tag: str | None = None) -> list[RawItem]:
    """ul#cagetory > li[id^=newslist-] > a[href][title], h2, p. No timestamps in the list."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select('li[id^="newslist-"]'):
        a = li.select_one("a[href]")
        if not a:
            continue
        title = str(a.get("title") or (li.select_one("h2") or a).get_text(" ", strip=True)).strip()
        p = li.select_one("p")
        out.append(
            RawItem(
                source_id=source_id,
                url=str(a["href"]),
                title=str(title),
                summary=p.get_text(" ", strip=True) if p else "",
                outlet="Moneycontrol",
                tag=tag,
            )
        )
    return out


# ------------------------------------------------------------------ corporate actions
def parse_corporate_action(html: str, source_id: str) -> list[RawItem]:
    data = next_data(html)["data"]
    out = []
    for day, rows in (data.get("filteredList") or {}).items():
        for r in rows:
            name, etype = r.get("stockName", ""), r.get("eventType", "")
            heading = r.get("heading") if r.get("heading") not in (None, "-") else ""
            purpose = r.get("purpose") if r.get("purpose") not in (None, "-") else ""
            title = f"{name}: {etype}" + (f" – {heading or purpose}" if heading or purpose else "")
            attach = r.get("attachment_url") if r.get("attachment_url") not in (None, "-") else None
            out.append(
                RawItem(
                    source_id=source_id,
                    url=attach or f"https://www.moneycontrol.com/markets/corporate-action/#{name}-{etype}-{day}",
                    title=title,
                    summary=str(r.get("summary") or "").strip("- "),
                    outlet="Moneycontrol",
                    published_at=_dmy(r.get("announcementDate")),
                    tag="corporate_action",
                    company_hint=name,
                    payload={"row": r, "list_date": day},
                )
            )
    return out


# ------------------------------------------------------------------ market stats (price / volume shockers)
def parse_market_stats(html: str, source_id: str, tag: str | None = "unusual_move") -> list[RawItem]:
    stats = next_data(html)["marketStatsData"]
    category = stats.get("category") or source_id
    rows = (stats.get("marketStatsOverviewData") or {}).get("list") or []
    label = str(category).replace("-", " ")
    out = []
    for r in rows:
        sym, name = r.get("symbol") or r.get("scId"), r.get("stockName", "")
        out.append(
            RawItem(
                source_id=source_id,
                url=r.get("shareUrl") or f"https://www.moneycontrol.com/india/stockpricequote/{r.get('slug', '')}",
                title=f"{name} ({sym}) in {label}: {r.get('perChange', '')} at {r.get('currentPrice', '')}",
                summary=f"Volume {r.get('volume', '')}, day range {r.get('low', '')}–{r.get('high', '')}, "
                f"prev close {r.get('prevClose', '')}",
                outlet="Moneycontrol",
                tag=tag,
                company_hint=sym,
                payload={"row": r, "category": category},
            )
        )
    return out


# ------------------------------------------------------------------ deals
def parse_deals(html: str, source_id: str) -> list[RawItem]:
    data = next_data(html)["data"]
    rows: list[dict[str, Any]] = []
    for group in ("topDeal", "topInsider", "topInvestor"):
        rows += (data.get("topWeeklyDealsData") or {}).get(group) or []
    seen, out = set(), []
    for r in rows:
        key = (r.get("ds_id"), r.get("boughtBy"))
        if key in seen:
            continue
        seen.add(key)
        qty, px = r.get("quantity"), r.get("deal_price")
        out.append(
            RawItem(
                source_id=source_id,
                url=f"https://www.moneycontrol.com/markets/stock-deals/#{r.get('ds_id')}",
                title=f"{r.get('stockName')}: {r.get('deal_type', 'deal')} {str(r.get('action', '')).lower()} "
                f"by {r.get('boughtBy', 'unknown')} ({qty:,} shares @ {px})"
                if qty and px
                else f"{r.get('stockName')}: {r.get('deal_type', 'deal')} {r.get('action', '')}",
                outlet="Moneycontrol",
                tag="bulk_block_deal",
                company_hint=r.get("stockName"),
                published_at=_iso(r.get("deal_date")),
                payload={"row": r},
            )
        )
    return out


# ------------------------------------------------------------------ earnings calendar
def parse_earnings_calendar(html: str, source_id: str) -> list[RawItem]:
    rows = (next_data(html)["earningsDashboardData"].get("resCalData") or {}).get("list") or []
    return [
        RawItem(
            source_id=source_id,
            url=r.get("stockUrl") or "https://www.moneycontrol.com/markets/earnings/",
            title=f"{r.get('stockName')} results ({r.get('resultType', '')}) scheduled on {r.get('date', '')}",
            summary=f"Time: {r.get('time', 'n/a')}",
            outlet="Moneycontrol",
            tag="results_scheduled",
            company_hint=r.get("stockName"),
            payload={"row": r},
        )
        for r in rows
    ]


# ------------------------------------------------------------------ FII / DII
def parse_fii_dii(html: str, source_id: str) -> list[RawItem]:
    rows = (next_data(html).get("FiiDiiData") or {}).get("fiiDiiData") or []
    return [
        RawItem(
            source_id=source_id,
            url=f"https://www.moneycontrol.com/markets/fii-dii-data/#{r.get('date')}",
            title=f"FII/DII cash flows {r.get('fDate')}: FII {r.get('fiiCM')} cr, DII {r.get('diiCM')} cr",
            outlet="Moneycontrol",
            tag="market_context",
            published_at=_iso(r.get("date")),
            payload={"row": r},
        )
        for r in rows[:1]
    ]  # latest day only; history lives in the payload store


def _dmy(s: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(s), "%d/%m/%Y").replace(tzinfo=IST) if s else None
    except ValueError:
        return None


def _iso(s: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").replace(tzinfo=IST) if s else None
    except ValueError:
        return None
