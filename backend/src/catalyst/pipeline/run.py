"""One pipeline run: due sources → raw items → de-dup → match → triage → verify → analyse → publish."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from catalyst.config import Settings, load_markets, load_sources, load_triage_rules, load_watchlist
from catalyst.pipeline.analysis import (
    collect_evidence,
    name_tokens,
    overlap,
    same_story,
    story_tokens,
    write_alert,
)
from catalyst.pipeline.matching import CompanyMatcher, dedupe
from catalyst.pipeline.triage import triage
from catalyst.providers.factory import Providers
from catalyst.schemas import Alert, Company, RawItem, Source, utcnow
from catalyst.sources.reader import is_due, read_source
from catalyst.store.base import Store

log = logging.getLogger("catalyst.run")


@dataclass
class RunStats:
    run_id: str
    started_at: datetime
    sources_run: list[str] = field(default_factory=list)
    fetched: int = 0
    new_items: int = 0
    matched: int = 0
    events: int = 0
    alerts: list[Alert] = field(default_factory=list)
    errors: dict[str, list[str]] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"run {self.run_id}: {len(self.sources_run)} sources, {self.fetched} fetched, {self.new_items} new, "
            f"{self.matched} matched, {self.events} events, {len(self.alerts)} alerts, "
            f"{sum(len(v) for v in self.errors.values())} errors"
        )


def _market_for(company: Company, source: Source) -> str:
    return source.market if source.market in company.markets else sorted(company.markets)[0]


def run_once(
    settings: Settings,
    providers: Providers,
    store: Store,
    *,
    force: bool = False,
    only: set[str] | None = None,
    now: datetime | None = None,
) -> RunStats:
    now = now or utcnow()
    stats = RunStats(run_id=uuid.uuid4().hex[:12], started_at=now)
    markets = load_markets()
    sources = {s.id: s for s in load_sources()}
    companies = load_watchlist()
    by_id = {c.id: c for c in companies}
    rules = load_triage_rules()
    matcher = CompanyMatcher(companies)
    last = store.last_runs()
    seen = store.seen_hashes()

    # 1) Watch: run every due source
    fresh: list[tuple[RawItem, Source]] = []
    for src in sources.values():
        if only and src.id not in only:
            continue
        if not force and not is_due(src, markets[src.market], last.get(src.id), now):
            continue
        res = read_source(src, providers.web, companies)
        stats.sources_run.append(src.id)
        stats.fetched += len(res.items)
        new = dedupe(res.items, seen)  # 2) De-dup
        store.save_raw(stats.run_id, new)
        store.record_run(stats.run_id, src.id, now, len(res.items), len(new), res.errors)
        if res.errors:
            stats.errors[src.id] = res.errors
            log.warning("source %s errors: %s", src.id, res.errors[:3])
        fresh += [(it, src) for it in new]
    stats.new_items = len(fresh)
    pool = [it for it, _ in fresh]

    # 3) Match → 4) Triage → 5) Verify → 6) Analyse → 7) Publish
    # Official sources first, then the most widely covered, so the best copy of a story becomes the event.
    fresh.sort(key=lambda p: (p[1].trust != "official", -p[0].related_count))
    quotes_cache: dict[str, dict[str, object]] = {}
    matches = {it.content_hash: matcher.match(it) for it, _ in fresh}
    stories: dict[str, list[tuple[set[str], str]]] = {}  # company -> (tokens, event_type) already turned into events
    for item, src in fresh:
        for cid in matches[item.content_hash]:
            stats.matched += 1
            company = by_id[cid]
            ignore = name_tokens(company)
            toks = story_tokens(item, ignore)
            if any(same_story(toks, t) for t, _ in stories.get(cid, [])):
                continue  # another copy of a story we already have; it shows up as evidence instead
            event = triage(item, src, cid, company.name, rules, providers.llm)
            if not event:
                continue
            # Same company + same kind of event + some word overlap in one run → same story.
            if any(et == event.event_type and overlap(toks, t) >= 0.2 for t, et in stories.get(cid, [])):
                continue
            stories.setdefault(cid, []).append((toks, event.event_type))
            store.save_event(event)
            stats.events += 1
            evidence = collect_evidence(event, item, pool, company_matches=matches, ignore=ignore)
            market = _market_for(company, src)
            quote = None
            try:
                if market not in quotes_cache:
                    lsts = [lst for c in companies for lst in c.listings if (lst.currency == "USD") == (market == "us")]
                    quotes_cache[market] = {
                        f"{q.exchange}:{q.symbol}": q for q in providers.prices[market].quotes(lsts)
                    }
                primary = next(lst for lst in company.listings if (lst.currency == "USD") == (market == "us"))
                quote = quotes_cache[market].get(f"{primary.exchange}:{primary.symbol}")
            except Exception as exc:  # noqa: BLE001 - prices are context, not required
                log.info("no quote for %s: %s", cid, exc)
            try:
                alert = write_alert(
                    event,
                    company,
                    market,
                    evidence,
                    providers.llm,
                    quote,  # type: ignore[arg-type]
                    mode=settings.catalyst_mode,
                )
            except Exception as exc:  # noqa: BLE001
                stats.errors.setdefault("analyst", []).append(f"{event.event_id}: {exc}")
                continue
            store.save_alert(alert)
            stats.alerts.append(alert)

    if providers.tinyfish:
        store.bump_usage("tinyfish", "search", providers.tinyfish.usage["search"])
        store.bump_usage("tinyfish", "fetch_urls", providers.tinyfish.usage["fetch_urls"])
    log.info(stats.summary())
    return stats
