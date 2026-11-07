# Catalyst Radar — Folder Structure

The real repo layout (kept in sync with the code).

```
catalyst-radar/
├── README.md                      # Quick start + docs index
├── aim.md · PLAN.md · PRINCIPLES.md · ARCHITECTURE.md · SOURCES.md · FOLDER_STRUCTURE.md
├── .env.example                   # Modes, providers, keys (copy to .env; never commit .env)
├── docker-compose.yml             # Optional local Postgres (default store is SQLite)
├── databricks.yml                 # Databricks Asset Bundle (Free Edition workspace)
├── resources/jobs/                # Bundle jobs (created PAUSED)
│   ├── catalyst_pipeline.yml      #   every 15 min 07:00–23:45 IST → 10_pipeline_run
│   ├── catalyst_prices.yml        #   every 5 min in market hours → 11_prices_run
│   └── catalyst_source_test.yml   #   on demand ("Test link" for custom sources) → 12_source_test
├── .github/workflows/ci.yml       # ruff + mypy + pytest (mock mode, no network)
│
├── config/                        # Data, not code
│   ├── markets/india.yaml         #   market settings + sources (Pulse, Moneycontrol, RSS, search, NSE, SEBI, stats…)
│   ├── markets/us.yaml            #   SEC EDGAR, search, CNBC
│   ├── watchlist.yaml             #   companies → listings (NSE/BSE/NYSE…), sector, asset class (equity/etf/commodity)
│   └── triage_rules.yaml          #   event types, keywords, base scores, boosts, threshold
│
├── databricks/
│   ├── sql/                       # Unity Catalog DDL (${catalog}/${prefix} filled by 00_setup)
│   │   ├── 01_schemas.sql         #   bronze · silver · gold · ops + landing volume
│   │   ├── 02_bronze.sql          #   raw_items
│   │   ├── 03_silver.sql          #   events · evidence · facts · price_quotes
│   │   ├── 04_ops.sql             #   source_runs · usage_events · companies · listings · sources + views
│   │   └── 05_gold.sql            #   alerts + v_latest_quotes · v_feed
│   └── notebooks/                 # Run from a Git folder (serverless); %pip install ../../backend
│       ├── 00_setup.py            #   catalog/schemas/tables + config → ops tables
│       ├── 01_probe_outbound.py   #   which hosts are reachable from Free Edition
│       ├── 10_pipeline_run.py     #   one pipeline run → Delta (mode mock|live)
│       ├── 11_prices_run.py       #   batched quotes → silver.price_quotes
│       └── 12_source_test.py      #   preview what a new source link yields
│
├── backend/                       # Python package `catalyst-radar` (uv, Python 3.12)
│   ├── pyproject.toml · uv.lock
│   ├── src/catalyst/
│   │   ├── config.py              #   Settings (env) + YAML loaders; mode → provider defaults
│   │   ├── schemas.py             #   Pydantic contracts: Source, Company, RawItem, Event, Evidence, Fact, Alert, PriceQuote…
│   │   ├── providers/             #   every outside service behind a switch
│   │   │   ├── web.py             #     MockReader · DirectReader · TinyFishReader · AutoReader (direct → Fetch)
│   │   │   ├── tinyfish.py        #     Search + Fetch client (retries, circuit breaker); no Agent
│   │   │   ├── llm.py             #     OpenAICompatLLM (LM Studio / Databricks) · ClaudeLLM · MockLLM
│   │   │   ├── prices.py          #     Mock · Yahoo (laptop) · Finnhub · Angel One (M3) · Unavailable
│   │   │   ├── resilience.py      #     circuit breaker + per-host pacing
│   │   │   └── factory.py         #     builds the provider set for the mode
│   │   ├── sources/
│   │   │   ├── pulse.py           #     Zerodha Pulse parser
│   │   │   ├── moneycontrol.py    #     news list + __NEXT_DATA__ market pages
│   │   │   ├── feeds.py           #     RSS · NSE JSON · SEC EDGAR · search hits
│   │   │   └── reader.py          #     is_due + run one configured source
│   │   ├── pipeline/
│   │   │   ├── matching.py        #     de-dup + company matcher (aliases, safe short tickers)
│   │   │   ├── triage.py          #     rules first, LLM for borderline items
│   │   │   ├── analysis.py        #     same-story merge, evidence, alert writing, citation enforcement
│   │   │   ├── run.py             #     orchestrator: run_once()
│   │   │   └── prompts/           #     triage.md · analyst.md
│   │   ├── analytics/
│   │   │   ├── indicators.py      #     SMA/EMA/RSI, S1–S3/R1–R3, 52-week, trend, circuit, returns
│   │   │   └── portfolio.py       #     sector trends, asset-class groups, bullish/bearish mood
│   │   ├── store/                 #     base (protocol) · sql (SQLite/Postgres/Lakebase) · delta (Databricks)
│   │   ├── mock_data/             #     SIMULATED pages in the real formats (Pulse, Moneycontrol, RSS, NSE, SEC, search)
│   │   ├── runtime.py             #     Databricks glue: secrets, workspace auth, catalog fallback
│   │   └── cli.py                 #     catalyst run | sources | probe | snapshot | alerts
│   └── tests/                     #   config · parsers · pipeline logic · analytics · end-to-end mock run
│
├── web/                           # Next.js website (M1b)
├── data/simulation/               # Simulation dataset (Excel + JSON) for mock mode
└── docs/
    ├── IMPLEMENTATION_PLAN.md     # Detailed tasks, status, Databricks steps
    ├── ARCHITECTURE-FREE-TIER.md  # Databricks Free Edition + Vercel
    ├── DESIGN.md · ui/prototype.html · brand/ (Kat)
    ├── architecture*.svg / *.eraserdiagram
    └── input.md                   # Feature requests (sectors, performance, S/R, circuits…)
```

## Why it's laid out this way
- **`config/`**: adding a source or market is a YAML edit, not code.
- **`providers/`**: each outside service has mock + real versions behind one interface, so mock / local / live share all pipeline code.
- **`sources/`**: one parser per site format, checked against real pages, tested on simulated ones.
- **`store/`**: the same pipeline writes to SQLite on the laptop and Delta on Databricks.
- **`databricks/` + bundle**: notebooks are thin entry points; all logic lives in the tested package.
