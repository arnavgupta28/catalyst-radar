"""Delta store for Databricks jobs (Unity Catalog tables created by databricks/sql/*.sql).

Append-only writes; the pipeline de-duplicates before writing, and runs are single-writer (one job run at a time).
Requires an active SparkSession (serverless notebook/job).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from catalyst.config import Settings
from catalyst.schemas import Alert, Event, PriceQuote, RawItem


class DeltaStore:
    def __init__(self, spark: Any, settings: Settings) -> None:
        self.spark = spark
        self.s = settings

    def _t(self, layer: str, name: str) -> str:
        return self.s.table(layer, name)

    def _append(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        schema = self.spark.table(table).schema
        df = self.spark.createDataFrame([{f.name: r.get(f.name) for f in schema.fields} for r in rows], schema)
        df.write.mode("append").saveAsTable(table)

    def seen_hashes(self, days: int = 14) -> set[str]:
        since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.spark.sql(
            f"SELECT content_hash FROM {self._t('bronze', 'raw_items')} WHERE fetched_at >= '{since}'"
        ).collect()
        return {r[0] for r in rows}

    def last_runs(self) -> dict[str, datetime]:
        rows = self.spark.sql(
            f"SELECT source_id, max(started_at) AS ts FROM {self._t('ops', 'source_runs')} GROUP BY source_id"
        ).collect()
        return {
            r["source_id"]: r["ts"].replace(tzinfo=UTC) if r["ts"].tzinfo is None else r["ts"]
            for r in rows
            if r["ts"] is not None
        }

    def record_run(
        self, run_id: str, source_id: str, started: datetime, items: int, new: int, errors: list[str]
    ) -> None:
        self._append(
            self._t("ops", "source_runs"),
            [
                {
                    "run_id": run_id,
                    "source_id": source_id,
                    "started_at": started,
                    "items": items,
                    "new_items": new,
                    "errors": json.dumps(errors),
                }
            ],
        )

    def save_raw(self, run_id: str, items: list[RawItem]) -> None:
        self._append(
            self._t("bronze", "raw_items"),
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
                    "related_urls": i.related_urls,
                    "tag": i.tag,
                    "company_hint": i.company_hint,
                    "payload": json.dumps(i.payload, default=str),
                    "fetched_at": i.fetched_at,
                }
                for i in items
            ],
        )

    def save_event(self, event: Event) -> None:
        self._append(self._t("silver", "events"), [event.model_dump()])

    def save_alert(self, alert: Alert) -> None:
        a = alert.model_dump()
        self._append(self._t("silver", "evidence"), [e.model_dump() for e in alert.evidence])
        self._append(
            self._t("silver", "facts"),
            [
                {
                    "event_id": alert.event_id,
                    "key": f.key,
                    "value": f.value,
                    "verification": f.verification,
                    "evidence_ids": f.evidence_ids,
                }
                for f in alert.facts
            ],
        )
        self._append(
            self._t("gold", "alerts"),
            [
                {
                    **{
                        k: a[k]
                        for k in (
                            "alert_id",
                            "event_id",
                            "company_id",
                            "market",
                            "priority",
                            "sentiment",
                            "headline",
                            "what_happened",
                            "why_it_matters",
                            "risks",
                            "bull_case",
                            "bear_case",
                            "next_steps",
                            "source_url",
                            "mode",
                            "model",
                            "created_at",
                        )
                    },
                    "body": alert.model_dump_json(),
                }
            ],
        )

    def save_quotes(self, quotes: list[PriceQuote]) -> None:
        self._append(self._t("silver", "price_quotes"), [q.model_dump() for q in quotes])

    def bump_usage(self, provider: str, metric: str, count: int) -> None:
        if count:
            self._append(
                self._t("ops", "usage_events"),
                [{"ts": datetime.now(UTC), "provider": provider, "metric": metric, "count": count}],
            )

    def recent_alerts(self, limit: int = 50) -> list[Alert]:
        rows = self.spark.sql(
            f"SELECT body FROM {self._t('gold', 'alerts')} ORDER BY created_at DESC LIMIT {int(limit)}"
        ).collect()
        return [Alert.model_validate_json(r[0]) for r in rows]
