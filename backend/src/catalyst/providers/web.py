"""Web readers: how we get a page's text. direct → TinyFish Fetch fallback, or mock fixtures."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from importlib import resources
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx

from catalyst.providers.resilience import CircuitBreaker, HostPacer
from catalyst.providers.tinyfish import SearchHit, TinyFishClient
from catalyst.schemas import SearchOptions


class BlockedError(RuntimeError):
    """The site refused or dropped us (403/429/timeout)."""


class WebReader(Protocol):
    name: str

    def get_text(self, url: str, method: str = "auto") -> str: ...

    def search(self, query: str, options: SearchOptions) -> list[SearchHit]: ...


# ------------------------------------------------------------------ direct HTTP
class DirectReader:
    name = "direct"

    def __init__(self, user_agent: str, timeout: float = 15, min_interval: float = 1.0) -> None:
        self._http = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"},
            timeout=timeout,
            follow_redirects=True,
        )
        self._pacer = HostPacer(min_interval)
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_text(self, url: str, method: str = "direct") -> str:
        host = httpx.URL(url).host
        breaker = self._breakers.setdefault(host, CircuitBreaker(threshold=3, open_seconds=900))
        breaker.guard(host)
        self._pacer.wait(url)
        try:
            resp = self._http.get(url)
        except httpx.TransportError as exc:
            breaker.failure()
            raise BlockedError(f"{host}: {type(exc).__name__}") from exc
        if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
            breaker.failure()
            raise BlockedError(f"{host}: HTTP {resp.status_code}")
        resp.raise_for_status()
        breaker.success()
        return resp.text

    def search(self, query: str, options: SearchOptions) -> list[SearchHit]:
        raise NotImplementedError("direct reader cannot search; use tinyfish")


# ------------------------------------------------------------------ TinyFish
class TinyFishReader:
    name = "tinyfish"

    def __init__(self, client: TinyFishClient) -> None:
        self.client = client

    def get_text(self, url: str, method: str = "tinyfish_fetch") -> str:
        results, errors = self.client.fetch([url], fmt="html")
        if results and results[0].text:
            return results[0].text
        code = errors[0].get("code") if errors else "empty"
        raise BlockedError(f"tinyfish fetch failed for {url}: {code}")

    def search(self, query: str, options: SearchOptions) -> list[SearchHit]:
        return self.client.search(
            query,
            domain_type=options.domain_type,
            recency_minutes=options.recency_minutes,
            location=options.location,
            language=options.language,
        )


class AutoReader:
    """direct first (cheapest); TinyFish Fetch when the site blocks us; TinyFish for search."""

    name = "auto"

    def __init__(self, direct: DirectReader, tinyfish: TinyFishReader | None) -> None:
        self.direct = direct
        self.tinyfish = tinyfish

    def get_text(self, url: str, method: str = "auto") -> str:
        if method == "tinyfish_fetch":
            if not self.tinyfish:
                raise BlockedError("source needs TinyFish Fetch but TINYFISH_API_KEY is not set")
            return self.tinyfish.get_text(url)
        try:
            return self.direct.get_text(url)
        except BlockedError:
            if method == "direct" or not self.tinyfish:
                raise
            return self.tinyfish.get_text(url)

    def search(self, query: str, options: SearchOptions) -> list[SearchHit]:
        if not self.tinyfish:
            raise BlockedError("search needs TINYFISH_API_KEY")
        return self.tinyfish.search(query, options)


# ------------------------------------------------------------------ mock
_MOCK_ROUTES: list[tuple[str, str]] = [
    (r"pulse\.zerodha\.com", "pulse.html"),
    (r"moneycontrol\.com/markets/corporate-action", "mc_corporate_action.html"),
    (r"moneycontrol\.com/stocks/market-stats", "mc_market_stats.html"),
    (r"moneycontrol\.com/markets/stock-deals", "mc_deals.html"),
    (r"moneycontrol\.com/markets/earnings", "mc_earnings_calendar.html"),
    (r"moneycontrol\.com/markets/fii-dii", "mc_fii_dii.html"),
    (r"moneycontrol\.com/news/", "mc_news_list.html"),
    (r"nseindia\.com/api/corporate-announcements", "nse_announcements.json"),
    (r"data\.sec\.gov/submissions", "sec_submissions.json"),
    (r"(rss|\.xml|\.cms)", "rss.xml"),
]
_TS = re.compile(r"\{\{(ts|iso|date|dmy|nsedt):(-?\d+)\}\}")


def render_mock(text: str, now: datetime | None = None) -> str:
    """Replace {{ts:-15}} style tokens with times relative to now (IST), so mock data looks fresh."""
    ist = ZoneInfo("Asia/Kolkata")
    now = (now or datetime.now(ist)).astimezone(ist)

    def sub(m: re.Match[str]) -> str:
        t = now + timedelta(minutes=int(m.group(2)))
        kind = m.group(1)
        if kind == "ts":  # Pulse style: 06:33 PM, 07 Nov 2026
            return t.strftime("%I:%M %p, %d %b %Y")
        if kind == "nsedt":  # NSE style: 16-Oct-2026 17:09:10
            return t.strftime("%d-%b-%Y %H:%M:%S")
        if kind == "date":
            return t.strftime("%Y-%m-%d")
        if kind == "dmy":  # Moneycontrol style: 07/11/2026
            return t.strftime("%d/%m/%Y")
        return t.isoformat()

    return _TS.sub(sub, text)


class MockReader:
    """Serves simulated pages in the real page formats (parsers can't tell the difference)."""

    name = "mock"

    def _file(self, name: str) -> str:
        return resources.files("catalyst.mock_data").joinpath(name).read_text(encoding="utf-8")

    def get_text(self, url: str, method: str = "auto") -> str:
        for pattern, fname in _MOCK_ROUTES:
            if re.search(pattern, url):
                return render_mock(self._file(fname))
        raise BlockedError(f"no mock page for {url}")

    def search(self, query: str, options: SearchOptions) -> list[SearchHit]:
        data: list[dict[str, Any]] = json.loads(render_mock(self._file("search_hits.json")))
        words = [
            w
            for w in re.findall(r"[a-z&]+", query.lower())
            if len(w) > 2 and w not in {"share", "news", "stock", "site"}
        ]
        hits = []
        for i, r in enumerate(data):
            text = f"{r['title']} {r['snippet']}".lower()
            if any(w in text for w in words):
                hits.append(
                    SearchHit(
                        url=r["url"],
                        title=r["title"],
                        snippet=r["snippet"],
                        site_name=r["site_name"],
                        position=i + 1,
                        published=r.get("date"),
                        raw=r,
                    )
                )
        return hits
