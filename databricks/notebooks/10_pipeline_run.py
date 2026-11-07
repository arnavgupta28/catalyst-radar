# Databricks notebook source
# MAGIC %md
# MAGIC # Catalyst Radar · 10 Pipeline run
# MAGIC One run: due sources → raw items → de-dup → match → triage → verify → analyse → alerts (Delta).
# MAGIC Used by the `catalyst-pipeline` job. `mode=mock` uses simulated pages and needs no secrets.

# COMMAND ----------

# MAGIC %pip install -q ../../backend

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

dbutils.widgets.dropdown("mode", "mock", ["mock", "live"], "Mode")  # noqa: F821
dbutils.widgets.text("catalog", "catalyst", "Catalog")  # noqa: F821
dbutils.widgets.text("prefix", "", "Schema prefix")  # noqa: F821
dbutils.widgets.dropdown("force", "false", ["false", "true"], "Run all sources now")  # noqa: F821
dbutils.widgets.text("only", "", "Only these source ids (comma-separated)")  # noqa: F821
w = {k: dbutils.widgets.get(k) for k in ("mode", "catalog", "prefix", "force", "only")}  # noqa: F821

import json
import logging

from catalyst.pipeline.run import run_once
from catalyst.providers.factory import build_providers
from catalyst.runtime import bootstrap
from catalyst.store.delta import DeltaStore

logging.basicConfig(level=logging.INFO)
settings = bootstrap(spark, dbutils, mode=w["mode"], catalog=w["catalog"], prefix=w["prefix"])  # noqa: F821
print(f"mode={settings.catalyst_mode} web={settings.resolved('web')} llm={settings.resolved('llm')} "
      f"prices={settings.resolved('price_in')}/{settings.resolved('price_us')}")

# COMMAND ----------

stats = run_once(settings, build_providers(settings), DeltaStore(spark, settings),  # noqa: F821
                 force=w["force"] == "true", only=set(w["only"].split(",")) if w["only"] else None)
print(stats.summary())
for a in stats.alerts:
    print(f"[{a.priority}] {a.company_id}: {a.headline}  ({len(a.evidence)} sources)")
for sid, errs in stats.errors.items():
    print(f"! {sid}: {errs[0]}")

# COMMAND ----------

dbutils.notebook.exit(json.dumps({  # noqa: F821
    "run_id": stats.run_id, "sources": len(stats.sources_run), "new_items": stats.new_items,
    "alerts": len(stats.alerts), "errors": {k: len(v) for k, v in stats.errors.items()}}))
