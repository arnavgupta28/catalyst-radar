"""Circuit breaker + polite per-host pacing, shared by HTTP-based providers."""

from __future__ import annotations

import threading
import time
from urllib.parse import urlparse


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; lets one call through after `open_seconds`."""

    def __init__(self, threshold: int = 3, open_seconds: float = 300) -> None:
        self.threshold = threshold
        self.open_seconds = open_seconds
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at > self.open_seconds:
            self.opened_at, self.failures = None, 0  # half-open
            return False
        return True

    def guard(self, name: str) -> None:
        if self.is_open:
            raise CircuitOpenError(f"{name} paused after repeated failures")

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class HostPacer:
    """Keeps at least `min_interval` seconds between requests to the same host."""

    def __init__(self, min_interval: float = 1.0) -> None:
        self.min_interval = min_interval
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        with self._lock:
            now = time.monotonic()
            delay = self._last.get(host, 0) + self.min_interval - now
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()
