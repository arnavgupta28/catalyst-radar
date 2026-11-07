"""Watchlist-level views: performance over day/week/month, bullish/bearish mood, sector trends, asset classes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from catalyst.analytics.indicators import Snapshot
from catalyst.schemas import Company

Mood = Literal["bullish", "bearish", "neutral"]


@dataclass
class GroupStats:
    name: str
    members: list[str] = field(default_factory=list)
    change_1d: float | None = None
    change_1w: float | None = None
    change_1m: float | None = None
    advancers: int = 0
    decliners: int = 0
    mood: Mood = "neutral"


def _avg(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _mood(change_1d: float | None, advancers: int, decliners: int) -> Mood:
    if change_1d is None:
        return "neutral"
    if change_1d > 0.25 and advancers >= decliners:
        return "bullish"
    if change_1d < -0.25 and decliners >= advancers:
        return "bearish"
    return "neutral"


def group_stats(name: str, snaps: dict[str, Snapshot]) -> GroupStats:
    g = GroupStats(name=name, members=sorted(snaps))
    g.change_1d = _avg([s.change_1d for s in snaps.values()])
    g.change_1w = _avg([s.change_1w for s in snaps.values()])
    g.change_1m = _avg([s.change_1m for s in snaps.values()])
    g.advancers = sum(1 for s in snaps.values() if (s.change_1d or 0) > 0)
    g.decliners = sum(1 for s in snaps.values() if (s.change_1d or 0) < 0)
    g.mood = _mood(g.change_1d, g.advancers, g.decliners)
    return g


def by_sector(companies: list[Company], snaps: dict[str, Snapshot]) -> list[GroupStats]:
    """Equal-weight sector performance across the watchlist, best 1-day first."""
    groups: dict[str, dict[str, Snapshot]] = defaultdict(dict)
    for c in companies:
        if c.id in snaps:
            groups[c.sector][c.id] = snaps[c.id]
    out = [group_stats(sector, members) for sector, members in groups.items()]
    return sorted(out, key=lambda g: g.change_1d if g.change_1d is not None else -999, reverse=True)


def by_asset_class(companies: list[Company], snaps: dict[str, Snapshot]) -> dict[str, GroupStats]:
    """Equities, ETFs and commodities shown separately."""
    groups: dict[str, dict[str, Snapshot]] = defaultdict(dict)
    for c in companies:
        if c.id in snaps:
            groups[c.asset_class][c.id] = snaps[c.id]
    return {k: group_stats(k, v) for k, v in groups.items()}
