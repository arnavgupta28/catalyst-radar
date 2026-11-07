from datetime import UTC, datetime, timedelta

import pytest

from catalyst.analytics.indicators import classic_pivots, fifty_two_week, pct_return, rsi, sma, snapshot, trend
from catalyst.analytics.portfolio import by_asset_class, by_sector
from catalyst.config import load_watchlist
from catalyst.providers.prices import MockPriceProvider
from catalyst.schemas import Candle


def c(close: float, high: float | None = None, low: float | None = None, day: int = 0) -> Candle:
    return Candle(
        ts=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day),
        open=close,
        high=high or close,
        low=low or close,
        close=close,
    )


def test_classic_pivots_known_values():
    p = classic_pivots(c(close=105, high=110, low=100))
    assert p.pivot == pytest.approx(105.0)
    assert (p.r1, p.s1) == (110.0, 100.0)
    assert (p.r2, p.s2) == (115.0, 95.0)
    assert (p.r3, p.s3) == (120.0, 90.0)
    assert p.s3 < p.s2 < p.s1 < p.pivot < p.r1 < p.r2 < p.r3


def test_sma_rsi_returns():
    closes = [float(x) for x in range(1, 31)]
    assert sma(closes, 5) == 28.0
    assert rsi(closes) == 100.0  # only gains
    assert rsi([10.0] * 5) is None  # not enough data
    assert pct_return([100.0, 110.0], 1) == 10.0
    assert trend(closes) == "flat"  # needs 50 sessions for the SMA50
    rising = [float(x) for x in range(1, 61)]
    assert trend(rising) == "up"
    assert trend(list(reversed(rising))) == "down"


def test_fifty_two_week_flags():
    candles = [c(100 + i % 10, day=i) for i in range(260)]
    w = fifty_two_week(candles, price=109.5)
    assert w.high == 109 and w.low == 100
    assert w.near_high and w.new_high and not w.near_low


def test_snapshot_with_mock_prices_and_circuit():
    p = MockPriceProvider()
    lst = load_watchlist()[0].listings[0]
    snap = snapshot(p.history(lst, 365), p.quotes([lst])[0])
    assert snap.circuit is not None and snap.circuit.band_pct == 10.0
    assert snap.pivots.s1 < snap.pivots.r1
    assert snap.trend in {"up", "down", "flat"}


def test_sector_and_asset_class_groups():
    companies = load_watchlist()
    p = MockPriceProvider()
    snaps = {}
    for co in companies:
        lst = co.listings[0]
        snaps[co.id] = snapshot(p.history(lst, 120), p.quotes([lst])[0])
    sectors = by_sector(companies, snaps)
    assert {s.name for s in sectors} >= {"Capital Goods", "Information Technology"}
    classes = by_asset_class(companies, snaps)
    assert set(classes) == {"equity", "etf", "commodity"}
    assert all(g.mood in {"bullish", "bearish", "neutral"} for g in classes.values())
