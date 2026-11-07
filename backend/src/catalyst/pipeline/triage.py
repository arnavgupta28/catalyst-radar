"""Cheap-first triage: keyword rules decide most items; the LLM only refines borderline ones."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from catalyst.providers.llm import LLM, MockLLM
from catalyst.schemas import Event, RawItem, Source, TriageVerdict

log = logging.getLogger("catalyst.triage")
_AMOUNT = re.compile(r"(₹|rs\.?|inr|\$|usd)\s?[\d,.]+\s?(crore|cr|lakh crore|billion|bn|million|mn)", re.I)


@lru_cache(maxsize=1024)
def _kw(keyword: str) -> re.Pattern[str]:
    """Whole-word keyword match (plurals allowed), so 'ban' doesn't fire inside 'HDFC Bank'
    but 'receives order' still matches 'receives orders'."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?:s|es)?(?![a-z0-9])")


@dataclass
class RuleScore:
    event_type: str
    score: int
    sentiment: str
    reason: str


def rule_score(item: RawItem, source: Source, rules: dict[str, Any]) -> RuleScore:
    text = f"{item.title} {item.summary}".lower()
    types: dict[str, dict[str, Any]] = rules["event_types"]
    matches = {et: [k for k in cfg["keywords"] if _kw(k).search(text)] for et, cfg in types.items()}
    matches = {et: hits for et, hits in matches.items() if hits}
    best: tuple[str, dict[str, Any], list[str]] | None = None
    if "routine" in matches:  # routine filings win: they're explicitly not catalysts
        best = ("routine", types["routine"], matches["routine"])
    else:
        if matches:
            et = max(matches, key=lambda e: types[e]["base"])
            best = (et, types[et], matches[et])
        if item.tag in types and (best is None or types[item.tag]["base"] >= best[1]["base"]):
            best = (item.tag, types[item.tag], [f"tag:{item.tag}"])
    if best is None:
        return RuleScore("news", 30, "neutral", "no rule matched")
    etype, cfg, hits = best
    score = int(cfg["base"])
    boosts = rules.get("boosts", {})
    reasons = [f"keywords: {', '.join(hits[:3])}"]
    if etype != "routine":
        if source.trust == "official":
            score += boosts.get("official_source", 0)
            reasons.append("official source")
        if item.related_count:
            score += boosts.get("multi_outlet", 0) * min(item.related_count, 3)
            reasons.append(f"{item.related_count + 1} outlets")
        if _AMOUNT.search(text):
            score += boosts.get("large_amount", 0)
            reasons.append("large amount mentioned")
    return RuleScore(etype, min(score, 100), cfg.get("sentiment", "neutral"), "; ".join(reasons))


def _prompt(name: str) -> str:
    return resources.files("catalyst.pipeline.prompts").joinpath(name).read_text(encoding="utf-8")


def triage(
    item: RawItem, source: Source, company_id: str, company_name: str, rules: dict[str, Any], llm: LLM
) -> Event | None:
    rs = rule_score(item, source, rules)
    threshold = int(rules.get("threshold", 55))
    if rs.event_type == "routine" or rs.score < threshold - 10:
        return None
    verdict_type, score, reason = rs.event_type, rs.score, rs.reason
    # Borderline items (within 10 points of the threshold) get a second opinion from the triage model.
    if rs.score < threshold + 10 or isinstance(llm, MockLLM):
        ctx = {"materiality": rs.score, "event_type": rs.event_type, "threshold": threshold}
        user = (
            f"Company: {company_name}\nSource: {source.name} (trust: {source.trust})\n"
            f"Headline: {item.title}\nSummary: {item.summary}\n"
            f"Rule guess: {rs.event_type}, score {rs.score} ({rs.reason})"
        )
        try:
            v = llm.complete_json("triage", _prompt("triage.md"), user, TriageVerdict, ctx)
            if not v.material:
                return None
            verdict_type, score, reason = v.event_type or rs.event_type, v.materiality, f"{rs.reason}; llm: {v.reason}"
        except Exception as exc:  # noqa: BLE001 - fall back to the rule result
            log.warning("triage LLM failed, using rules: %s", exc)
    if score < threshold:
        return None
    event_id = hashlib.sha256(f"{item.content_hash}|{company_id}".encode()).hexdigest()[:24]
    return Event(
        event_id=event_id,
        content_hash=item.content_hash,
        company_id=company_id,
        source_id=source.id,
        trust=source.trust,
        event_type=verdict_type,
        materiality=score,
        sentiment_hint=rs.sentiment if rs.sentiment in {"positive", "negative", "mixed", "neutral"} else "neutral",  # type: ignore[arg-type]
        reason=reason,
        title=item.title,
        url=item.url,
        summary=item.summary,
        published_at=item.published_at,
    )
