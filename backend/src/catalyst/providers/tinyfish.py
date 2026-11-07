"""TinyFish Search + Fetch client (sync). The paid Agent is deliberately not wrapped.

- Search  GET  https://api.search.tinyfish.ai   free up to 12,000 requests/day
- Fetch   POST https://api.fetch.tinyfish.ai    free up to 1,000 URLs/day, max 10 URLs per call
Docs: https://docs.tinyfish.ai/search-api · https://docs.tinyfish.ai/fetch-api
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from catalyst.providers.resilience import CircuitBreaker

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"


class TinyFishError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str
    site_name: str
    position: int
    published: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    url: str
    final_url: str
    title: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)


class TinyFishClient:
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str, timeout: float = 45, user_agent: str = "CatalystRadar/0.1") -> None:
        if not api_key:
            raise RuntimeError("TINYFISH_API_KEY is not set")
        self._http = httpx.Client(headers={"X-API-Key": api_key, "User-Agent": user_agent}, timeout=timeout)
        self.breakers = {"search": CircuitBreaker(), "fetch": CircuitBreaker()}
        self.usage = {"search": 0, "fetch_urls": 0}

    def close(self) -> None:
        self._http.close()

    def _request(self, product: str, method: str, url: str, retries: int = 2, **kw: Any) -> dict[str, Any]:
        breaker = self.breakers[product]
        breaker.guard(f"tinyfish.{product}")
        for attempt in range(retries + 1):
            try:
                resp = self._http.request(method, url, **kw)
            except httpx.TransportError as exc:
                if attempt < retries:
                    time.sleep(0.5 * 2**attempt)
                    continue
                breaker.failure()
                raise TinyFishError(f"{product} unreachable: {type(exc).__name__}") from exc
            if resp.status_code in self.RETRY_STATUSES and attempt < retries:
                time.sleep(min(float(resp.headers.get("Retry-After", 0.5 * 2**attempt)), 5))
                continue
            if resp.status_code >= 400:
                body = _json(resp)
                err = body.get("error") if isinstance(body.get("error"), dict) else {}
                code = (err or {}).get("code") or body.get("code")
                if resp.status_code >= 500 or resp.status_code == 429:
                    breaker.failure()
                raise TinyFishError(f"{product} HTTP {resp.status_code} {code or ''}".strip(), resp.status_code, code)
            breaker.success()
            return _json(resp)
        raise TinyFishError(f"{product} failed after retries")

    def search(
        self,
        query: str,
        *,
        domain_type: str = "news",
        recency_minutes: int | None = None,
        location: str | None = None,
        language: str | None = None,
        purpose: str | None = None,
    ) -> list[SearchHit]:
        params: dict[str, Any] = {"query": query, "domain_type": domain_type}
        for k, v in {
            "recency_minutes": recency_minutes,
            "location": location,
            "language": language,
            "purpose": purpose,
        }.items():
            if v is not None:
                params[k] = v
        data = self._request("search", "GET", SEARCH_URL, params=params)
        self.usage["search"] += 1
        hits = []
        for r in data.get("results", []):
            if not r.get("url"):
                continue
            hits.append(
                SearchHit(
                    url=r["url"],
                    title=r.get("title") or "",
                    snippet=r.get("snippet") or "",
                    site_name=r.get("site_name") or r.get("publisher") or "",
                    position=r.get("position") or 0,
                    published=r.get("date") or r.get("published_date") or r.get("published"),
                    raw=r,
                )
            )
        return hits

    def fetch(
        self, urls: list[str], fmt: str = "html", ttl: int | None = None, include_selectors: list[str] | None = None
    ) -> tuple[list[FetchResult], list[dict[str, Any]]]:
        body: dict[str, Any] = {"urls": urls[:10], "format": fmt}
        if ttl is not None:
            body["ttl"] = ttl
        if include_selectors:
            body["include_selectors"] = include_selectors[:20]
        data = self._request("fetch", "POST", FETCH_URL, retries=1, json=body)
        self.usage["fetch_urls"] += len(body["urls"])
        results = [
            FetchResult(
                url=r.get("url", ""),
                final_url=r.get("final_url") or r.get("url", ""),
                title=r.get("title") or "",
                text=r.get("text") or "",
                raw=r,
            )
            for r in data.get("results", [])
        ]
        return results, data.get("errors", [])


def _json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"result": data}
    except ValueError:
        return {}
