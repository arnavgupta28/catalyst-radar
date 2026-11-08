# Databricks notebook source
# MAGIC %md
# MAGIC # Catalyst Radar · 00 Setup
# MAGIC Run once (safe to re-run). It:
# MAGIC 1. installs the `catalyst-radar` package from this Git folder,
# MAGIC 2. creates the catalog (or falls back to `workspace.catalyst_*`), schemas, volume and tables from `databricks/sql/*.sql`,
# MAGIC 3. mirrors `config/*.yaml` (companies, listings, sources) into `ops` tables.

# COMMAND ----------

# MAGIC %pip install -q ../../backend

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

dbutils.widgets.text("catalog", "catalyst", "Preferred catalog")  # noqa: F821

import re

from catalyst.config import find_repo_root, load_sources, load_watchlist
from catalyst.runtime import resolve_catalog

catalog, prefix = resolve_catalog(spark, dbutils.widgets.get("catalog"))  # noqa: F821
print(f"Using catalog={catalog!r} schema prefix={prefix!r}")

# COMMAND ----------

repo_root = find_repo_root()
sql_dir = repo_root / "databricks" / "sql"
sql_files = sorted(sql_dir.glob("*.sql"))
assert sql_files, f"No DDL files found in {sql_dir}"
print(f"Repo root: {repo_root}")
for path in sql_files:
    text = path.read_text().replace("${catalog}", catalog).replace("${prefix}", prefix)
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    statements = [s.strip() for s in re.split(r";\s*(?:\n|$)", text) if s.strip()]
    for stmt in statements:
        spark.sql(stmt)  # noqa: F821
    print(f"✓ {path.name}: {len(statements)} statements")

# COMMAND ----------


def overwrite(table: str, rows: list[dict]) -> None:
    full = f"{catalog}.{prefix}ops.{table}"
    schema = spark.table(full).schema  # noqa: F821
    df = spark.createDataFrame([{f.name: r.get(f.name) for f in schema.fields} for r in rows], schema)  # noqa: F821
    df.write.mode("overwrite").saveAsTable(full)
    print(f"✓ {full}: {len(rows)} rows")


companies = load_watchlist()
overwrite("companies", [c.model_dump(exclude={"listings"}) for c in companies])
overwrite("listings", [{"company_id": c.id, **lst.model_dump()} for c in companies for lst in c.listings])
overwrite("sources", [s.model_dump(exclude={"search", "query"}) for s in load_sources(include_disabled=True)])

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {catalog}.{prefix}silver"))  # noqa: F821
print(f"""
Done. Jobs and notebooks should use:
  catalog = {catalog}
  prefix  = {prefix!r}
Next: create the `catalyst` secret scope (see docs/IMPLEMENTATION_PLAN.md), then run 01_probe_outbound and 10_pipeline_run.
""")
