"""SQLAlchemy Core store. SQLite for laptop/tests, Postgres via docker-compose, Lakebase later (same SQL)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from catalyst.schemas import Alert, Event, PriceQuote, RawItem

md = MetaData()

source_runs = Table(
    "source_runs",
    md,
    Column("run_id", String(40)),
    Column("source_id", String(80), index=True),
    Column("started_at", DateTime(timezone=True)),
    Column("items", Integer),
    Column("new_items", Integer),
    Column("errors", Text),
)

raw_items = Table(
    "raw_items",
    md,
    Column("content_hash", String(32), primary_key=True),
    Column("run_id", String(40)),
    Column("source_id", String(80), index=True),
    Column("url", Text),
    Column("title", Text),
    Column("summary", Text),
    Column("outlet", String(120)),
    Column("published_at", DateTime(timezone=True)),
    Column("related_count", Integer),
    Column("tag", String(40)),
    Column("company_hint", String(120)),
    Column("payload", Text),
    Column("fetched_at", DateTime(timezone=True), index=True),
)

events = Table(
    "events",
    md,
    Column("event_id", String(24), primary_key=True),
    Column("content_hash", String(32)),
    Column("company_id", String(80), index=True),
    Column("source_id", String(80)),
    Column("trust", String(20)),
    Column("event_type", String(40)),
    Column("materiality", Integer),
    Column("sentiment_hint", String(20)),
    Column("reason", Text),
    Column("title", Text),
    Column("url", Text),
    Column("summary", Text),
    Column("published_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True)),
)

alerts = Table(
    "alerts",
    md,
    Column("alert_id", String(40), primary_key=True),
    Column("event_id", String(24)),
    Column("company_id", String(80), index=True),
    Column("market", String(20)),
    Column("priority", String(10)),
    Column("sentiment", String(20)),
    Column("headline", Text),
    Column("body", Text),
    Column("mode", String(10)),
    Column("model", String(120)),
    Column("created_at", DateTime(timezone=True), index=True),
)

quotes = Table(
    "price_quotes",
    md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String(40), index=True),
    Column("exchange", String(10)),
    Column("currency", String(5)),
    Column("price", String(32)),
    Column("body", Text),
    Column("provider", String(20)),
    Column("ts", DateTime(timezone=True)),
)

usage = Table(
    "usage_counters",
    md,
    Column("day", String(10), primary_key=True),
    Column("provider", String(40), primary_key=True),
    Column("metric", String(40), primary_key=True),
    Column("count", Integer),
)


class SqlStore:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, future=True)
        md.create_all(self.engine)

    def seen_hashes(self, days: int = 14) -> set[str]:
        since = datetime.now(UTC) - timedelta(days=days)
        with self.engine.connect() as c:
            return {r[0] for r in c.execute(select(raw_items.c.content_hash).where(raw_items.c.fetched_at >= since))}

    def last_runs(self) -> dict[str, datetime]:
        with self.engine.connect() as c:
            rows = c.execute(
                select(source_runs.c.source_id, func.max(source_runs.c.started_at)).group_by(source_runs.c.source_id)
            )
            out = {}
            for sid, ts in rows:
                if ts is not None:
                    out[sid] = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
            return out

    def record_run(
        self, run_id: str, source_id: str, started: datetime, items: int, new: int, errors: list[str]
    ) -> None:
        with self.engine.begin() as c:
            c.execute(
                insert(source_runs).values(
                    run_id=run_id,
                    source_id=source_id,
                    started_at=started,
                    items=items,
                    new_items=new,
                    errors=json.dumps(errors),
                )
            )

    def save_raw(self, run_id: str, items: list[RawItem]) -> None:
        if not items:
            return
        with self.engine.begin() as c:
            c.execute(
                insert(raw_items),
                [
                    {
                        "content_hash": i.content_hash,
                        "run_id": run_id,
                        "source_id": i.source_id,
                        "url": i.url,
                        "title": i.title,
                        "summary": i.summary,
                        "outlet": i.outlet,
                        "published_at": i.published_at,
                        "related_count": i.related_count,
                        "tag": i.tag,
                        "company_hint": i.company_hint,
                        "payload": json.dumps(i.payload, default=str),
                        "fetched_at": i.fetched_at,
                    }
                    for i in items
                ],
            )

    def save_event(self, event: Event) -> None:
        with self.engine.begin() as c:
            if c.execute(select(events.c.event_id).where(events.c.event_id == event.event_id)).first():
                return
            c.execute(insert(events).values(**event.model_dump()))

    def save_alert(self, alert: Alert) -> None:
        row = {
            "alert_id": alert.alert_id,
            "event_id": alert.event_id,
            "company_id": alert.company_id,
            "market": alert.market,
            "priority": alert.priority,
            "sentiment": alert.sentiment,
            "headline": alert.headline,
            "body": alert.model_dump_json(),
            "mode": alert.mode,
            "model": alert.model,
            "created_at": alert.created_at,
        }
        with self.engine.begin() as c:
            if c.execute(select(alerts.c.alert_id).where(alerts.c.alert_id == alert.alert_id)).first():
                c.execute(update(alerts).where(alerts.c.alert_id == alert.alert_id).values(**row))
            else:
                c.execute(insert(alerts).values(**row))

    def save_quotes(self, qs: list[PriceQuote]) -> None:
        if not qs:
            return
        with self.engine.begin() as c:
            c.execute(
                insert(quotes),
                [
                    {
                        "symbol": q.symbol,
                        "exchange": q.exchange,
                        "currency": q.currency,
                        "price": str(q.price),
                        "body": q.model_dump_json(),
                        "provider": q.provider,
                        "ts": q.ts,
                    }
                    for q in qs
                ],
            )

    def bump_usage(self, provider: str, metric: str, count: int) -> None:
        if not count:
            return
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        key = (usage.c.day == day) & (usage.c.provider == provider) & (usage.c.metric == metric)
        with self.engine.begin() as c:
            row = c.execute(select(usage.c.count).where(key)).first()
            if row:
                c.execute(update(usage).where(key).values(count=row[0] + count))
            else:
                c.execute(insert(usage).values(day=day, provider=provider, metric=metric, count=count))

    def recent_alerts(self, limit: int = 50) -> list[Alert]:
        with self.engine.connect() as c:
            rows = c.execute(select(alerts.c.body).order_by(alerts.c.created_at.desc()).limit(limit))
            return [Alert.model_validate_json(r[0]) for r in rows]

    def usage_today(self) -> dict[str, int]:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        with self.engine.connect() as c:
            return {
                f"{p}.{m}": n
                for p, m, n in c.execute(
                    select(usage.c.provider, usage.c.metric, usage.c.count).where(usage.c.day == day)
                )
            }
