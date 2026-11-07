"""Databricks runtime glue: load secrets into env, pick catalog/schema names, build settings + store."""

from __future__ import annotations

import logging
import os
from typing import Any

from catalyst.config import Settings, get_settings

log = logging.getLogger("catalyst.runtime")

SECRET_SCOPE = "catalyst"
SECRET_KEYS = [
    "tinyfish_api_key",
    "finnhub_api_key",
    "anthropic_api_key",
    "angelone_api_key",
    "angelone_client_code",
    "angelone_pin",
    "angelone_totp_secret",
    "databricks_triage_model",
    "databricks_writer_model",
]


def load_secrets(dbutils: Any, scope: str = SECRET_SCOPE) -> list[str]:
    """Copy secrets from the `catalyst` scope into env vars (missing keys are skipped). Returns loaded names."""
    loaded: list[str] = []
    try:
        available = {s.key for s in dbutils.secrets.list(scope)}
    except Exception:  # noqa: BLE001 - scope not created yet: run in mock mode without secrets
        log.warning("secret scope %r not found; continuing without secrets", scope)
        return loaded
    for key in SECRET_KEYS:
        if key in available:
            os.environ[key.upper()] = dbutils.secrets.get(scope, key)
            loaded.append(key)
    return loaded


def workspace_auth(dbutils: Any) -> None:
    """Let jobs call Model Serving with the run's own identity (no personal token needed)."""
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    os.environ.setdefault("DATABRICKS_HOST", f"https://{ctx.browserHostName().get()}")
    os.environ.setdefault("DATABRICKS_TOKEN", ctx.apiToken().get())


def bootstrap(spark: Any, dbutils: Any, mode: str = "live", catalog: str = "catalyst", prefix: str = "") -> Settings:
    os.environ["CATALYST_MODE"] = mode
    os.environ["CATALYST_CATALOG"] = catalog
    os.environ["CATALYST_SCHEMA_PREFIX"] = prefix
    load_secrets(dbutils)
    try:
        workspace_auth(dbutils)
    except Exception as exc:  # noqa: BLE001 - not fatal outside notebooks
        log.info("workspace auth not available: %s", exc)
    get_settings.cache_clear()
    return get_settings()


def resolve_catalog(spark: Any, preferred: str = "catalyst") -> tuple[str, str]:
    """Use a dedicated catalog if we can create it; otherwise fall back to the default `workspace`
    catalog with prefixed schemas (catalyst_bronze, ...). Returns (catalog, schema_prefix)."""
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {preferred}")
        spark.sql(f"USE CATALOG {preferred}")
        return preferred, ""
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot create catalog %s (%s); falling back to workspace.catalyst_*", preferred, exc)
        return "workspace", "catalyst_"
