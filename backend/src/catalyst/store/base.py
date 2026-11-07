"""What the pipeline needs from storage. Implemented by SqlStore (local) and DeltaStore (Databricks)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from catalyst.schemas import Alert, Event, PriceQuote, RawItem


class Store(Protocol):
    def seen_hashes(self, days: int = 14) -> set[str]: ...

    def last_runs(self) -> dict[str, datetime]: ...

    def record_run(
        self, run_id: str, source_id: str, started: datetime, items: int, new: int, errors: list[str]
    ) -> None: ...

    def save_raw(self, run_id: str, items: list[RawItem]) -> None: ...

    def save_event(self, event: Event) -> None: ...

    def save_alert(self, alert: Alert) -> None: ...

    def save_quotes(self, quotes: list[PriceQuote]) -> None: ...

    def bump_usage(self, provider: str, metric: str, count: int) -> None: ...

    def recent_alerts(self, limit: int = 50) -> list[Alert]: ...
