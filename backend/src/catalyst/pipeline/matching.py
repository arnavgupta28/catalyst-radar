"""De-duplication and company matching."""

from __future__ import annotations

import re
from collections.abc import Iterable

from catalyst.schemas import Company, RawItem


def dedupe(items: Iterable[RawItem], seen: set[str]) -> list[RawItem]:
    """Drop items whose content hash we've already stored (or seen earlier in this batch)."""
    out = []
    for it in items:
        h = it.content_hash
        if h in seen:
            continue
        seen.add(h)
        out.append(it)
    return out


class CompanyMatcher:
    """Finds which watchlist companies an item is about.

    Names/aliases match case-insensitively on word boundaries; short tickers (<= 4 chars, e.g. "LT", "BEL")
    match only as exact UPPERCASE words, so "bel" in a sentence doesn't match Bharat Electronics.
    """

    def __init__(self, companies: list[Company]) -> None:
        self.companies = {c.id: c for c in companies}
        self._patterns: list[tuple[str, re.Pattern[str]]] = []
        self._hints: dict[str, str] = {}
        for c in companies:
            terms = {c.name, *c.aliases}
            for t in sorted(terms, key=len, reverse=True):
                if len(t) <= 4 and t.isupper():
                    pat = re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])")
                else:
                    pat = re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", re.I)
                self._patterns.append((c.id, pat))
            self._hints[c.id.lower()] = c.id
            self._hints[c.name.lower()] = c.id
            for a in c.aliases:
                self._hints[a.lower()] = c.id
            for lst in c.listings:
                self._hints[lst.symbol.lower()] = c.id

    def match(self, item: RawItem) -> list[str]:
        if item.company_hint:
            cid = self._hints.get(item.company_hint.lower())
            if cid:
                return [cid]
        text = f"{item.title} {item.summary}"
        found: list[str] = []
        for cid, pat in self._patterns:
            if cid not in found and pat.search(text):
                found.append(cid)
        return found
