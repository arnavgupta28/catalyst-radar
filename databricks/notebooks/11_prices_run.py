# Databricks notebook source
# MAGIC %md
# MAGIC # Catalyst Radar · 11 Prices
# MAGIC One batched quote call per market for every watchlist listing → `silver.price_quotes`.
# MAGIC Used by the `catalyst-prices` job (market hours only).

# COMMAND ----------

# MAGIC %pip install -q ../../backend

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

dbutils.widgets.dropdown("mode", "mock", ["mock", "live"], "Mode")  # noqa: F821
dbutils.widgets.text("catalog", "catalyst", "Catalog")  # noqa: F821
dbutils.widgets.text("prefix", "", "Schema prefix")  # noqa: F821
w = {k: dbutils.widgets.get(k) for k in ("mode", "catalog", "prefix")}  # noqa: F821

from catalyst.config import load_watchlist
from catalyst.providers.factory import build_price
from catalyst.runtime import bootstrap
from catalyst.store.delta import DeltaStore

settings = bootstrap(spark, dbutils, mode=w["mode"], catalog=w["catalog"], prefix=w["prefix"])  # noqa: F821
store = DeltaStore(spark, settings)  # noqa: F821
companies = load_watchlist()

# COMMAND ----------

total = 0
for market, kind in (("india", settings.resolved("price_in")), ("us", settings.resolved("price_us"))):
    listings = [lst for c in companies for lst in c.listings if (lst.currency == "USD") == (market == "us")]
    try:
        quotes = build_price(kind, settings).quotes(listings)
        store.save_quotes(quotes)
        total += len(quotes)
        print(f"✓ {market}: {len(quotes)} quotes from {kind}")
    except Exception as exc:  # noqa: BLE001 - one market failing must not stop the other
        print(f"! {market} ({kind}): {exc}")
dbutils.notebook.exit(str(total))  # noqa: F821
