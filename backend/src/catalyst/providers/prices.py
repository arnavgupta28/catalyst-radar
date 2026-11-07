"""Price providers behind one interface. Batched quotes + daily history for analytics."""

from __future__ import annotations

import hashlib
import math
import random
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from catalyst.schemas import Candle, Listing, PriceQuote


class PriceProvider(Protocol):
    name: str

    def quotes(self, listings: list[Listing]) -> list[PriceQuote]: ...

    def history(self, listing: Listing, days: int = 365) -> list[Candle]: ...


# ------------------------------------------------------------------ mock
_BASE = {
    "LT": 3640.0,
    "BEL": 412.0,
    "INFY": 1520.0,
    "HDFCBANK": 1712.0,
    "RELIANCE": 2890.0,
    "NIFTYBEES": 268.0,
    "GOLDBEES": 98.0,
    "GOLD": 121500.0,
    "AAPL": 228.0,
    "NVDA": 131.0,
}


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)


class MockPriceProvider:
    """Deterministic geometric random walk per symbol: same day → same history, so tests are stable."""

    name = "mock"

    def __init__(self, today: datetime | None = None) -> None:
        self.today = (today or datetime.now(UTC)).replace(hour=0, minute=0, second=0, microsecond=0)

    def _base(self, lst: Listing) -> float:
        if lst.symbol in _BASE:
            return _BASE[lst.symbol] / (83.0 if lst.currency == "USD" and lst.exchange == "NYSE" else 1)
        return 100 + _seed(lst.symbol) % 900

    def history(self, listing: Listing, days: int = 365) -> list[Candle]:
        rng = random.Random(_seed(listing.exchange, listing.symbol, self.today.date().isoformat()))
        price = self._base(listing) * (0.8 + rng.random() * 0.2)
        out: list[Candle] = []
        for i in range(days, 0, -1):
            day = self.today - timedelta(days=i)
            if day.weekday() >= 5:
                continue
            drift = rng.gauss(0.0004, 0.016)
            open_ = price
            close = max(1.0, price * math.exp(drift))
            high = max(open_, close) * (1 + abs(rng.gauss(0, 0.006)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, 0.006)))
            out.append(
                Candle(
                    ts=day,
                    open=round(open_, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=float(rng.randint(2_00_000, 90_00_000)),
                )
            )
            price = close
        return out

    def quotes(self, listings: list[Listing]) -> list[PriceQuote]:
        out = []
        for lst in listings:
            hist = self.history(lst, days=10)
            last, prev = hist[-1], hist[-2]
            band = 0.10 if lst.currency == "INR" else None
            out.append(
                PriceQuote(
                    symbol=lst.symbol,
                    exchange=lst.exchange,
                    currency=lst.currency,
                    price=last.close,
                    prev_close=prev.close,
                    change_pct=round((last.close / prev.close - 1) * 100, 2),
                    day_high=last.high,
                    day_low=last.low,
                    volume=last.volume,
                    upper_circuit=round(prev.close * (1 + band), 2) if band else None,
                    lower_circuit=round(prev.close * (1 - band), 2) if band else None,
                    provider=self.name,
                )
            )
        return out


# ------------------------------------------------------------------ Yahoo (unofficial; laptop only)
class YahooProvider:
    """Unofficial Yahoo chart API. Rate-limited (429) from Databricks shared IPs, so local mode only."""

    name = "yfinance"
    URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def __init__(self, user_agent: str) -> None:
        self._http = httpx.Client(headers={"User-Agent": user_agent}, timeout=15)

    def _chart(self, symbol: str, rng: str, interval: str) -> dict[str, Any]:
        resp = self._http.get(self.URL.format(symbol=symbol), params={"range": rng, "interval": interval})
        resp.raise_for_status()
        return resp.json()["chart"]["result"][0]

    def history(self, listing: Listing, days: int = 365) -> list[Candle]:
        res = self._chart(listing.yahoo or listing.symbol, "1y" if days > 180 else "6mo", "1d")
        q = res["indicators"]["quote"][0]
        out = []
        for i, ts in enumerate(res.get("timestamp", [])):
            if q["close"][i] is None:
                continue
            out.append(
                Candle(
                    ts=datetime.fromtimestamp(ts, UTC),
                    open=q["open"][i],
                    high=q["high"][i],
                    low=q["low"][i],
                    close=q["close"][i],
                    volume=q["volume"][i] or 0,
                )
            )
        return out[-days:]

    def quotes(self, listings: list[Listing]) -> list[PriceQuote]:
        out = []
        for lst in listings:
            meta = self._chart(lst.yahoo or lst.symbol, "5d", "1d")["meta"]
            price, prev = meta.get("regularMarketPrice"), meta.get("chartPreviousClose")
            out.append(
                PriceQuote(
                    symbol=lst.symbol,
                    exchange=lst.exchange,
                    currency=lst.currency,
                    price=price,
                    prev_close=prev,
                    change_pct=round((price / prev - 1) * 100, 2) if price and prev else None,
                    day_high=meta.get("regularMarketDayHigh"),
                    day_low=meta.get("regularMarketDayLow"),
                    volume=meta.get("regularMarketVolume"),
                    provider=self.name,
                    delayed=True,
                )
            )
        return out


# ------------------------------------------------------------------ Finnhub (US)
class FinnhubProvider:
    name = "finnhub"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise RuntimeError("FINNHUB_API_KEY is not set")
        self._http = httpx.Client(timeout=15, params={"token": api_key})

    def quotes(self, listings: list[Listing]) -> list[PriceQuote]:
        out = []
        for lst in listings:
            d = self._http.get("https://finnhub.io/api/v1/quote", params={"symbol": lst.symbol}).json()
            out.append(
                PriceQuote(
                    symbol=lst.symbol,
                    exchange=lst.exchange,
                    currency=lst.currency,
                    price=d["c"],
                    prev_close=d.get("pc"),
                    change_pct=d.get("dp"),
                    day_high=d.get("h"),
                    day_low=d.get("l"),
                    provider=self.name,
                )
            )
        return out

    def history(self, listing: Listing, days: int = 365) -> list[Candle]:
        raise NotImplementedError("Finnhub candles are not on the free plan; history comes from the dataset/Yahoo")


# ------------------------------------------------------------------ Angel One (India, M3)
class AngelOneProvider:
    """SmartAPI with TOTP auto-login. Implemented in milestone M3 (needs the account + API key)."""

    name = "angelone"

    def __init__(self, *_: object, **__: object) -> None:
        raise NotImplementedError("Angel One provider arrives in M3; use PRICE_PROVIDER_IN=mock or yfinance")

    def quotes(self, listings: list[Listing]) -> list[PriceQuote]:  # pragma: no cover
        raise NotImplementedError

    def history(self, listing: Listing, days: int = 365) -> list[Candle]:  # pragma: no cover
        raise NotImplementedError


class UnavailablePriceProvider:
    """Stands in when a provider can't be built (missing key, not implemented yet). Every call explains why."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = f"{name} (unavailable)"
        self.reason = reason

    def quotes(self, listings: list[Listing]) -> list[PriceQuote]:
        raise RuntimeError(f"{self.name}: {self.reason}")

    def history(self, listing: Listing, days: int = 365) -> list[Candle]:
        raise RuntimeError(f"{self.name}: {self.reason}")
