# Databricks notebook source
# MAGIC %md
# MAGIC # Catalyst Radar · 01 Probe outbound access
# MAGIC Free Edition only allows some outbound domains. This checks every host our sources and providers use.
# MAGIC Blocked hosts are read through TinyFish Fetch instead (sources with `method: auto` do this automatically).

# COMMAND ----------

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CatalystRadar/0.1"}
URLS = [
    "https://pulse.zerodha.com/",
    "https://www.moneycontrol.com/news/business/markets/",
    "https://www.moneycontrol.com/stocks/market-stats/price-shockers-nse/",
    "https://www.moneycontrol.com/markets/corporate-action/",
    "https://groww.in/markets/top-gainers",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.livemint.com/rss/markets",
    "https://www.sebi.gov.in/sebirss.xml",
    "https://www.nseindia.com/",
    "https://data.sec.gov/submissions/CIK0001045810.json",
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://api.search.tinyfish.ai/",
    "https://api.fetch.tinyfish.ai/",
    "https://finnhub.io/",
    "https://apiconnect.angelone.in/",
    "https://api.anthropic.com/",
]
rows = []
for u in URLS:
    try:
        r = requests.get(u, headers=HEADERS, timeout=10)
        rows.append((u, "OK", r.status_code, len(r.text), "__NEXT_DATA__" in r.text))
    except Exception as exc:  # noqa: BLE001
        rows.append((u, "BLOCKED", None, None, type(exc).__name__))
display(spark.createDataFrame(  # noqa: F821
    [(a, b, c, d, str(e)) for a, b, c, d, e in rows], "url string, result string, status int, bytes int, note string"))
