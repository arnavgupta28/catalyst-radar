"""Typed contracts between pipeline steps. Same shapes as the Delta / SQL tables."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

Trust = Literal["official", "news", "context", "unverified"]
Method = Literal["direct", "tinyfish_fetch", "tinyfish_search", "auto"]
AssetClass = Literal["equity", "etf", "commodity"]
Sentiment = Literal["positive", "negative", "mixed", "neutral"]
Priority = Literal["High", "Medium", "Low"]
Verification = Literal["confirmed", "conflicting", "unconfirmed"]


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- config models
class Market(BaseModel):
    id: str
    name: str
    flag: str = ""
    currency: str
    timezone: str
    open: str
    close: str
    exchanges: list[str]
    price_providers: list[str] = Field(default_factory=list)


class SearchOptions(BaseModel):
    domain_type: Literal["web", "news", "research_paper"] = "news"
    recency_minutes: int | None = 1440
    location: str | None = None
    language: str | None = None


_INTERVAL = re.compile(r"^(\d+)\s*([mhd])$")


class Source(BaseModel):
    id: str
    name: str
    market: str = ""
    url: str | None = None
    parser: str
    method: Method = "auto"
    trust: Trust = "news"
    interval: str = "15m"
    active_hours: str | None = None
    scope: Literal["market", "company"] = "market"
    exchange: str | None = None
    tag: str | None = None
    query: str | None = None
    search: SearchOptions | None = None
    enabled: bool = True
    builtin: bool = True

    @property
    def interval_seconds(self) -> int:
        m = _INTERVAL.match(self.interval.strip())
        if not m:
            raise ValueError(f"bad interval {self.interval!r} for source {self.id}")
        n, unit = int(m.group(1)), m.group(2)
        return n * {"m": 60, "h": 3600, "d": 86400}[unit]


class Listing(BaseModel):
    exchange: str
    symbol: str
    currency: str
    yahoo: str | None = None
    cik: str | None = None


class Company(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    sector: str = "Unknown"
    industry: str = ""
    asset_class: AssetClass = "equity"
    listings: list[Listing]

    @property
    def markets(self) -> set[str]:
        return {"us" if lst.currency == "USD" else "india" for lst in self.listings}


# ---------------------------------------------------------------- pipeline models
class RawItem(BaseModel):
    """One thing a source said: a headline, a filing, a stats row."""

    source_id: str
    url: str
    title: str
    summary: str = ""
    published_at: datetime | None = None
    outlet: str | None = None
    related_count: int = 0
    related_urls: list[str] = Field(default_factory=list)
    tag: str | None = None
    company_hint: str | None = None  # symbol/company id when the source is per-company
    payload: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utcnow)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        norm = re.sub(r"\W+", " ", self.title.lower()).strip()
        return hashlib.sha256(f"{norm}|{self.url.split('#')[0]}".encode()).hexdigest()[:32]


class Event(BaseModel):
    event_id: str
    content_hash: str
    company_id: str
    source_id: str
    trust: Trust
    event_type: str
    materiality: int
    sentiment_hint: Sentiment = "neutral"
    reason: str = ""
    title: str
    url: str
    summary: str = ""
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Evidence(BaseModel):
    evidence_id: str
    event_id: str
    url: str
    source_id: str
    outlet: str | None = None
    excerpt: str = ""
    captured_at: datetime = Field(default_factory=utcnow)


class Fact(BaseModel):
    key: str
    value: str
    verification: Verification = "unconfirmed"
    evidence_ids: list[str] = Field(default_factory=list)


class AlertDraft(BaseModel):
    """What the writer LLM must return (validated)."""

    sentiment: Sentiment
    priority: Priority
    headline: str
    what_happened: str
    why_it_matters: str
    risks: str
    bull_case: str
    bear_case: str
    next_steps: str
    facts: list[Fact] = Field(default_factory=list)


class TriageVerdict(BaseModel):
    """What the triage LLM must return."""

    material: bool
    event_type: str
    materiality: int = Field(ge=0, le=100)
    reason: str


class Alert(AlertDraft):
    alert_id: str
    event_id: str
    company_id: str
    market: str
    source_url: str
    evidence: list[Evidence] = Field(default_factory=list)
    mode: str = "mock"
    model: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    disclaimer: str = "Research, not investment advice."


class PriceQuote(BaseModel):
    symbol: str
    exchange: str
    currency: str
    price: float
    prev_close: float | None = None
    change_pct: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: float | None = None
    upper_circuit: float | None = None
    lower_circuit: float | None = None
    provider: str
    delayed: bool = False
    ts: datetime = Field(default_factory=utcnow)


class Candle(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
