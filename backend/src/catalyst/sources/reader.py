"""Runs one configured source: decide if it's due, build URL(s), fetch, parse → RawItems."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from catalyst.providers.web import WebReader
from catalyst.schemas import Company, Market, RawItem, SearchOptions, Source, utcnow
from catalyst.sources import feeds, groww, moneycontrol, pulse

log = logging.getLogger("catalyst.sources")

Parser = Callable[[str, Source, str | None], list[RawItem]]

PARSERS: dict[str, Parser] = {
    "pulse": lambda text, src, hint: pulse.parse_pulse(text, src.id),
    "mc_news_list": lambda text, src, hint: moneycontrol.parse_news_list(text, src.id, src.tag),
    "mc_corporate_action": lambda text, src, hint: moneycontrol.parse_corporate_action(text, src.id),
    "mc_market_stats": lambda text, src, hint: moneycontrol.parse_market_stats(text, src.id, src.tag),
    "mc_deals": lambda text, src, hint: moneycontrol.parse_deals(text, src.id),
    "mc_earnings_calendar": lambda text, src, hint: moneycontrol.parse_earnings_calendar(text, src.id),
    "mc_fii_dii": lambda text, src, hint: moneycontrol.parse_fii_dii(text, src.id),
    "groww_market": lambda text, src, hint: groww.parse_groww_market(text, src.id, src.tag),
    "rss": lambda text, src, hint: feeds.parse_rss(text, src.id),
    "nse_announcements": lambda text, src, hint: feeds.parse_nse_announcements(text, src.id, hint),
    "sec_submissions": lambda text, src, hint: feeds.parse_sec_submissions(text, src.id, hint),
}


def _in_active_hours(src: Source, market: Market, now: datetime) -> bool:
    if not src.active_hours:
        return True
    start_s, end_s = src.active_hours.split("-")
    local = now.astimezone(ZoneInfo(market.timezone))
    start, end = time.fromisoformat(start_s), time.fromisoformat(end_s)
    return start <= local.time() <= end


def is_due(src: Source, market: Market, last_run: datetime | None, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if not src.enabled or not _in_active_hours(src, market, now):
        return False
    return last_run is None or (now - last_run).total_seconds() >= src.interval_seconds


@dataclass
class SourceResult:
    source_id: str
    items: list[RawItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requests: int = 0


def companies_for(src: Source, companies: list[Company]) -> list[Company]:
    return [c for c in companies if src.market in c.markets]


def read_source(src: Source, web: WebReader, companies: list[Company]) -> SourceResult:
    res = SourceResult(src.id)

    def tag(items: list[RawItem]) -> list[RawItem]:
        for it in items:
            it.tag = it.tag or src.tag
        return items

    # -------- per-company search (TinyFish Search, free)
    if src.method == "tinyfish_search":
        opts = src.search or SearchOptions()
        for c in companies_for(src, companies):
            query = (src.query or "{name}").format(name=c.name, symbol=c.listings[0].symbol)
            try:
                hits = web.search(query, opts)
                res.requests += 1
                res.items += tag(feeds.hits_to_items(hits, src.id, c.id))
            except Exception as exc:  # noqa: BLE001 - one company failing must not stop the rest
                res.errors.append(f"{c.id}: {exc}")
        return res

    parser = PARSERS.get(src.parser)
    if parser is None or not src.url:
        res.errors.append(f"no parser/url for {src.id}")
        return res

    # -------- per-company URL templates (NSE symbol, SEC CIK)
    if src.scope == "company" and "{" in src.url:
        for c in companies_for(src, companies):
            for lst in c.listings:
                if src.exchange and lst.exchange != src.exchange:
                    continue
                if "{cik}" in src.url and not lst.cik:
                    continue
                if src.market == "us" and lst.currency != "USD":
                    continue
                url = src.url.format(symbol=lst.symbol, cik=(lst.cik or "").zfill(10))
                try:
                    text = web.get_text(url, src.method)
                    res.requests += 1
                    items = parser(text, src, lst.symbol)
                    for it in items:
                        it.company_hint = it.company_hint or c.id
                    res.items += tag(items)
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(f"{c.id}/{lst.symbol}: {exc}")
        return res

    # -------- one page for the whole market
    try:
        text = web.get_text(src.url, src.method)
        res.requests += 1
        res.items = tag(parser(text, src, None))
    except Exception as exc:  # noqa: BLE001
        res.errors.append(str(exc))
    return res
