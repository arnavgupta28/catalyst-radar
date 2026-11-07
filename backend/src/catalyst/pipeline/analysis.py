"""Verify (collect corroborating evidence) and Analyse (LLM writes the alert; every fact must cite evidence)."""

from __future__ import annotations

import hashlib
import re
from importlib import resources

from catalyst.providers.llm import LLM
from catalyst.schemas import Alert, AlertDraft, Company, Event, Evidence, PriceQuote, RawItem

_WORD = re.compile(r"[a-z0-9]{4,}")


_STOP = {
    "shares",
    "share",
    "stock",
    "stocks",
    "today",
    "after",
    "with",
    "from",
    "says",
    "india",
    "ltd",
    "limited",
    "company",
    "news",
    "worth",
    "crore",
}


def title_tokens(s: str) -> set[str]:
    return set(_WORD.findall(s.lower())) - _STOP


def story_tokens(item: RawItem, ignore: set[str] | None = None) -> set[str]:
    """Headline + summary words, minus the company's own name words (which every story about it shares).
    Filings ('Bagging of orders') and news ('wins metro order') share few headline words but their summaries overlap."""
    return title_tokens(f"{item.title} {item.summary}") - (ignore or set())


def name_tokens(company: Company) -> set[str]:
    return title_tokens(" ".join([company.name, *company.aliases]))


def overlap(a: set[str], b: set[str]) -> float:
    """Overlap relative to the shorter set, so a short headline inside a long one still matches."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def same_story(a: set[str], b: set[str], min_overlap: float = 0.45) -> bool:
    return overlap(a, b) >= min_overlap


def _eid(event_id: str, url: str) -> str:
    return "ev_" + hashlib.sha256(f"{event_id}|{url}".encode()).hexdigest()[:10]


def collect_evidence(
    event: Event,
    item: RawItem,
    pool: list[RawItem],
    min_overlap: float = 0.3,
    company_matches: dict[str, list[str]] | None = None,
    ignore: set[str] | None = None,
) -> list[Evidence]:
    """The item itself + Pulse 'similar' coverage + other items in this run that tell the same story."""
    ev = [
        Evidence(
            evidence_id=_eid(event.event_id, item.url),
            event_id=event.event_id,
            url=item.url,
            source_id=item.source_id,
            outlet=item.outlet,
            excerpt=(item.summary or item.title)[:400],
        )
    ]
    seen = {item.url}
    for url, outlet in zip(item.related_urls, item.payload.get("related_outlets", []) or [None] * 99, strict=False):
        if url not in seen:
            seen.add(url)
            ev.append(
                Evidence(
                    evidence_id=_eid(event.event_id, url),
                    event_id=event.event_id,
                    url=url,
                    source_id=item.source_id,
                    outlet=outlet,
                    excerpt="Related coverage (Pulse)",
                )
            )
    base = story_tokens(item, ignore)
    for other in pool:
        if other.url in seen or not base:
            continue
        if company_matches is not None and event.company_id not in company_matches.get(other.content_hash, []):
            continue  # only corroborate with items about the same company
        if same_story(base, story_tokens(other, ignore), min_overlap):
            seen.add(other.url)
            ev.append(
                Evidence(
                    evidence_id=_eid(event.event_id, other.url),
                    event_id=event.event_id,
                    url=other.url,
                    source_id=other.source_id,
                    outlet=other.outlet,
                    excerpt=(other.summary or other.title)[:400],
                )
            )
    return ev


def enforce_citations(draft: AlertDraft, evidence: list[Evidence]) -> AlertDraft:
    """Grounding rule: facts may only cite evidence we actually hold; uncited facts become 'unconfirmed'."""
    known = {e.evidence_id for e in evidence}
    for f in draft.facts:
        f.evidence_ids = [i for i in f.evidence_ids if i in known]
        if not f.evidence_ids:
            f.verification = "unconfirmed"
    return draft


def _prompt(name: str) -> str:
    return resources.files("catalyst.pipeline.prompts").joinpath(name).read_text(encoding="utf-8")


def write_alert(
    event: Event,
    company: Company,
    market: str,
    evidence: list[Evidence],
    llm: LLM,
    quote: PriceQuote | None = None,
    mode: str = "mock",
) -> Alert:
    ev_lines = "\n".join(f"- [{e.evidence_id}] {e.outlet or e.source_id}: {e.excerpt} ({e.url})" for e in evidence)
    price_line = (
        f"Price: {quote.price} {quote.currency} ({quote.change_pct:+.2f}% today)"
        if quote and quote.change_pct is not None
        else "Price: n/a"
    )
    user = (
        f"Company: {company.name} ({', '.join(f'{lst.exchange}:{lst.symbol}' for lst in company.listings)})\n"
        f"Sector: {company.sector} / {company.industry}\n{price_line}\n"
        f"Event type: {event.event_type} (materiality {event.materiality}; {event.reason})\n"
        f"Headline: {event.title}\nSummary: {event.summary}\n\nEvidence (cite by id):\n{ev_lines}"
    )
    ctx = {
        "company": company.name,
        "title": event.title,
        "event_type": event.event_type,
        "sentiment_hint": event.sentiment_hint,
        "materiality": event.materiality,
        "evidence": [e.model_dump() for e in evidence],
    }
    draft = llm.complete_json("writer", _prompt("analyst.md"), user, AlertDraft, ctx)
    draft = enforce_citations(draft, evidence)
    return Alert(
        **draft.model_dump(),
        alert_id="al_" + event.event_id[:20],
        event_id=event.event_id,
        company_id=company.id,
        market=market,
        source_url=event.url,
        evidence=evidence,
        mode=mode,
        model=llm.model_for("writer"),
    )
