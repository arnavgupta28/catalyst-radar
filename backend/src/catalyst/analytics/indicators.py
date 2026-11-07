"""Pure functions on daily candles. No I/O, fully unit-tested.

Covers the docs/input.md requests: 3 support + 3 resistance levels (classic pivots, the style Groww shows),
52-week high/low proximity, trend arrow + indicators (SMA/EMA/RSI), circuit %, returns over day/week/month.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from catalyst.schemas import Candle, PriceQuote

Trend = Literal["up", "down", "flat"]


def sma(values: list[float], n: int) -> float | None:
    return sum(values[-n:]) / n if len(values) >= n else None


def ema(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e


def rsi(values: list[float], n: int = 14) -> float | None:
    """Wilder's RSI."""
    if len(values) <= n:
        return None
    gains = [max(values[i] - values[i - 1], 0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0) for i in range(1, len(values))]
    avg_g, avg_l = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l_ in zip(gains[n:], losses[n:], strict=True):
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l_) / n
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


@dataclass
class Pivots:
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


def classic_pivots(prev: Candle) -> Pivots:
    """Classic floor pivots from the previous session's high/low/close."""
    h, l_, c = prev.high, prev.low, prev.close
    p = (h + l_ + c) / 3
    return Pivots(
        pivot=round(p, 2),
        r1=round(2 * p - l_, 2),
        s1=round(2 * p - h, 2),
        r2=round(p + (h - l_), 2),
        s2=round(p - (h - l_), 2),
        r3=round(h + 2 * (p - l_), 2),
        s3=round(l_ - 2 * (h - p), 2),
    )


@dataclass
class FiftyTwoWeek:
    high: float
    low: float
    pct_from_high: float  # negative = below the high
    pct_from_low: float
    near_high: bool
    near_low: bool
    new_high: bool
    new_low: bool


def fifty_two_week(candles: list[Candle], price: float, near_pct: float = 2.0) -> FiftyTwoWeek:
    window = candles[-252:]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    from_hi = (price / hi - 1) * 100
    from_lo = (price / lo - 1) * 100
    return FiftyTwoWeek(
        high=round(hi, 2),
        low=round(lo, 2),
        pct_from_high=round(from_hi, 2),
        pct_from_low=round(from_lo, 2),
        near_high=from_hi >= -near_pct,
        near_low=from_lo <= near_pct,
        new_high=price >= hi,
        new_low=price <= lo,
    )


def pct_return(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions:
        return None
    return round((closes[-1] / closes[-1 - sessions] - 1) * 100, 2)


def trend(closes: list[float]) -> Trend:
    """Up if price > SMA20 > SMA50, down if price < SMA20 < SMA50, else flat."""
    s20, s50 = sma(closes, 20), sma(closes, 50)
    if s20 is None or s50 is None:
        return "flat"
    p = closes[-1]
    if p > s20 > s50:
        return "up"
    if p < s20 < s50:
        return "down"
    return "flat"


@dataclass
class Circuit:
    upper: float | None
    lower: float | None
    band_pct: float | None  # e.g. 10 for a 10% band
    to_upper_pct: float | None
    to_lower_pct: float | None


def circuit(q: PriceQuote) -> Circuit:
    if not (q.upper_circuit and q.lower_circuit and q.prev_close):
        return Circuit(q.upper_circuit, q.lower_circuit, None, None, None)
    band = round((q.upper_circuit / q.prev_close - 1) * 100, 1)
    return Circuit(
        q.upper_circuit,
        q.lower_circuit,
        band,
        round((q.upper_circuit / q.price - 1) * 100, 2),
        round((1 - q.lower_circuit / q.price) * 100, 2),
    )


@dataclass
class Snapshot:
    """Everything the watchlist row / deep dive needs for one listing."""

    price: float
    change_1d: float | None
    change_1w: float | None
    change_1m: float | None
    trend: Trend
    sma20: float | None
    sma50: float | None
    sma200: float | None
    rsi14: float | None
    pivots: Pivots
    w52: FiftyTwoWeek
    circuit: Circuit | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def snapshot(candles: list[Candle], quote: PriceQuote | None = None) -> Snapshot:
    if len(candles) < 2:
        raise ValueError("need at least 2 candles")
    closes = [c.close for c in candles]
    price = quote.price if quote else closes[-1]
    series = [*closes[:-1], price] if quote else closes
    return Snapshot(
        price=round(price, 2),
        change_1d=pct_return(series, 1),
        change_1w=pct_return(series, 5),
        change_1m=pct_return(series, 21),
        trend=trend(series),
        sma20=_r(sma(series, 20)),
        sma50=_r(sma(series, 50)),
        sma200=_r(sma(series, 200)),
        rsi14=_r(rsi(series)),
        pivots=classic_pivots(candles[-2] if quote else candles[-1]),
        w52=fifty_two_week(candles, price),
        circuit=circuit(quote) if quote else None,
    )


def _r(x: float | None) -> float | None:
    return round(x, 2) if x is not None else None
