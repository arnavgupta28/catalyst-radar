# Databricks notebook source
# MAGIC %md
# MAGIC # Catalyst Radar · 12 Source test
# MAGIC "Test link" for a new source: fetch the page (direct, then TinyFish Fetch) and show what the parser finds.
# MAGIC Used by the `catalyst-source-test` job (the website's *Add source* button will trigger it).

# COMMAND ----------

# MAGIC %pip install -q ../../backend

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

dbutils.widgets.text("url", "https://pulse.zerodha.com/", "URL")  # noqa: F821
dbutils.widgets.dropdown(  # noqa: F821
    "parser", "pulse",
    ["pulse", "groww_market", "mc_news_list", "mc_corporate_action", "mc_market_stats", "mc_deals", "mc_earnings_calendar",
     "mc_fii_dii", "rss", "nse_announcements", "sec_submissions"], "Parser")
dbutils.widgets.dropdown("method", "auto", ["auto", "direct", "tinyfish_fetch"], "Method")  # noqa: F821
w = {k: dbutils.widgets.get(k) for k in ("url", "parser", "method")}  # noqa: F821

import json

from catalyst.config import load_watchlist
from catalyst.providers.factory import build_web
from catalyst.runtime import bootstrap
from catalyst.schemas import Source
from catalyst.sources.reader import read_source

settings = bootstrap(spark, dbutils, mode="live")  # noqa: F821
web, _ = build_web(settings)
src = Source(id="source_test", name="Source test", market="india", url=w["url"], parser=w["parser"],
             method=w["method"], trust="unverified", builtin=False)
res = read_source(src, web, load_watchlist())
print(f"{len(res.items)} items, {len(res.errors)} errors {res.errors[:1]}")
for it in res.items[:10]:
    print(f"- {it.title[:100]}  [{it.outlet}] {it.published_at or ''}")

# COMMAND ----------

dbutils.notebook.exit(json.dumps({  # noqa: F821
    "items": len(res.items), "errors": res.errors[:3],
    "preview": [{"title": i.title, "url": i.url, "outlet": i.outlet} for i in res.items[:5]]}))
