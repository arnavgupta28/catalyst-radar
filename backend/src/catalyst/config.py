"""Settings (from env / .env) and the YAML config: markets, sources, watchlist, triage rules."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from catalyst.schemas import Company, Market, Source

Mode = Literal["mock", "local", "live"]


def find_repo_root(start: Path | None = None) -> Path:
    """Find the repo root (the folder containing config/markets).

    Searched upward from: an explicit start, the package file (editable/dev installs), and the current
    directory. The last one matters on Databricks: `%pip install ../../backend` copies the package into
    site-packages, but the notebook's working directory is inside the Git folder.
    """
    env = os.environ.get("CATALYST_REPO_ROOT")
    if env:
        return Path(env)
    starts = [p for p in (start, Path(__file__), Path.cwd()) if p is not None]
    for s in starts:
        here = s.resolve()
        for parent in [here, *here.parents]:
            if (parent / "config" / "markets").is_dir():
                return parent
    raise FileNotFoundError(
        "Could not find the repo's config/markets folder (searched up from "
        f"{', '.join(str(s) for s in starts)}). Run from inside the repo / Git folder, "
        "or set CATALYST_REPO_ROOT to the repo path."
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    catalyst_mode: Mode = "mock"
    web_provider: str | None = None
    price_provider_in: str | None = None
    price_provider_us: str | None = None
    llm_provider: str | None = None

    database_url: str = "sqlite:///data/local/catalyst.sqlite"
    catalyst_catalog: str = "catalyst"
    catalyst_schema_prefix: str = ""

    tinyfish_api_key: str = ""
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CatalystRadar/0.1"

    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_triage_model: str = "qwen3-1.7b"
    lmstudio_writer_model: str = "qwen3-4b"
    databricks_host: str = ""
    databricks_token: str = ""
    databricks_triage_model: str = ""
    databricks_writer_model: str = ""
    anthropic_api_key: str = ""
    claude_triage_model: str = "claude-haiku-5-5"
    claude_writer_model: str = "claude-sonnet-5-5"

    finnhub_api_key: str = ""
    angelone_api_key: str = ""
    angelone_client_code: str = ""
    angelone_pin: str = ""
    angelone_totp_secret: str = ""

    # ------------------------------------------------------------ resolved providers
    def resolved(self, kind: str) -> str:
        explicit = {
            "web": self.web_provider,
            "price_in": self.price_provider_in,
            "price_us": self.price_provider_us,
            "llm": self.llm_provider,
        }[kind]
        if explicit:
            return explicit
        defaults = {
            "mock": {"web": "mock", "price_in": "mock", "price_us": "mock", "llm": "mock"},
            "local": {"web": "auto", "price_in": "yfinance", "price_us": "finnhub", "llm": "lmstudio"},
            "live": {"web": "auto", "price_in": "angelone", "price_us": "finnhub", "llm": "databricks"},
        }
        return defaults[self.catalyst_mode][kind]

    def table(self, layer: str, name: str) -> str:
        """Fully qualified Unity Catalog table name, e.g. catalyst.bronze.raw_items."""
        return f"{self.catalyst_catalog}.{self.catalyst_schema_prefix}{layer}.{name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ------------------------------------------------------------------ YAML config
def _load_yaml(path: Path) -> Any:
    with path.open() as f:
        return yaml.safe_load(f)


def config_dir() -> Path:
    return find_repo_root() / "config"


def load_markets() -> dict[str, Market]:
    out: dict[str, Market] = {}
    for p in sorted((config_dir() / "markets").glob("*.yaml")):
        m = Market(**_load_yaml(p)["market"])
        out[m.id] = m
    return out


def load_sources(include_disabled: bool = False) -> list[Source]:
    out: list[Source] = []
    for p in sorted((config_dir() / "markets").glob("*.yaml")):
        data = _load_yaml(p)
        market_id = data["market"]["id"]
        for raw in data.get("sources", []):
            src = Source(market=market_id, **raw)
            if src.enabled or include_disabled:
                out.append(src)
    ids = [s.id for s in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate source ids: {sorted(dupes)}")
    return out


def load_watchlist() -> list[Company]:
    data = _load_yaml(config_dir() / "watchlist.yaml")
    return [Company(**c) for c in data["companies"]]


def load_triage_rules() -> dict[str, Any]:
    return _load_yaml(config_dir() / "triage_rules.yaml")
