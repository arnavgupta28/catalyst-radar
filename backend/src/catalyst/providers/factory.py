"""Builds the provider set for the current mode (mock / local / live) and per-provider overrides."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from catalyst.config import Settings
from catalyst.providers.llm import LLM, ClaudeLLM, MockLLM, OpenAICompatLLM
from catalyst.providers.prices import (
    AngelOneProvider,
    FinnhubProvider,
    MockPriceProvider,
    PriceProvider,
    UnavailablePriceProvider,
    YahooProvider,
)
from catalyst.providers.tinyfish import TinyFishClient
from catalyst.providers.web import AutoReader, DirectReader, MockReader, TinyFishReader, WebReader

log = logging.getLogger("catalyst.providers")


@dataclass
class Providers:
    web: WebReader
    llm: LLM
    prices: dict[str, PriceProvider] = field(default_factory=dict)  # market id -> provider
    tinyfish: TinyFishClient | None = None


def build_web(settings: Settings) -> tuple[WebReader, TinyFishClient | None]:
    kind = settings.resolved("web")
    if kind == "mock":
        return MockReader(), None
    tf = (
        TinyFishClient(settings.tinyfish_api_key, user_agent=settings.user_agent) if settings.tinyfish_api_key else None
    )
    tf_reader = TinyFishReader(tf) if tf else None
    if kind == "tinyfish":
        if not tf_reader:
            raise RuntimeError("WEB_PROVIDER=tinyfish needs TINYFISH_API_KEY")
        return tf_reader, tf
    return AutoReader(DirectReader(settings.user_agent), tf_reader), tf


def build_llm(settings: Settings) -> LLM:
    kind = settings.resolved("llm")
    if kind == "mock":
        return MockLLM()
    if kind == "lmstudio":
        return OpenAICompatLLM(
            "lmstudio", settings.lmstudio_base_url, "", settings.lmstudio_triage_model, settings.lmstudio_writer_model
        )
    if kind == "databricks":
        host = settings.databricks_host.rstrip("/")
        return OpenAICompatLLM(
            "databricks",
            f"{host}/serving-endpoints",
            settings.databricks_token,
            settings.databricks_triage_model,
            settings.databricks_writer_model,
        )
    if kind == "claude":
        return ClaudeLLM(settings.anthropic_api_key, settings.claude_triage_model, settings.claude_writer_model)
    raise ValueError(f"unknown LLM provider {kind!r}")


def build_price(kind: str, settings: Settings) -> PriceProvider:
    if kind == "mock":
        return MockPriceProvider()
    if kind == "yfinance":
        return YahooProvider(settings.user_agent)
    if kind == "finnhub":
        return FinnhubProvider(settings.finnhub_api_key)
    if kind == "angelone":
        return AngelOneProvider(settings)
    raise ValueError(f"unknown price provider {kind!r}")


def _price_or_unavailable(kind: str, settings: Settings) -> PriceProvider:
    """Prices are context for alerts, not required: a missing key/provider must not stop the pipeline."""
    try:
        return build_price(kind, settings)
    except (NotImplementedError, RuntimeError) as exc:
        log.warning("price provider %s unavailable: %s", kind, exc)
        return UnavailablePriceProvider(kind, str(exc))


def build_providers(settings: Settings) -> Providers:
    web, tf = build_web(settings)
    return Providers(
        web=web,
        llm=build_llm(settings),
        prices={
            "india": _price_or_unavailable(settings.resolved("price_in"), settings),
            "us": _price_or_unavailable(settings.resolved("price_us"), settings),
        },
        tinyfish=tf,
    )
