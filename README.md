# Catalyst Radar

Watches the companies you follow, reads the filings and news for you, and tells you **what changed, why it matters, and where the proof is**.

A personal project to explore web agents, LLMs and market data, and to use daily. Research, not investment advice.

## What's here

| Path | What |
|---|---|
| [backend/](backend/) | Python package `catalyst-radar`: sources, parsers, pipeline, providers, analytics, stores, CLI |
| [config/](config/) | Market packs (sources per market), watchlist, triage rules (data, not code) |
| [databricks/](databricks/) | Unity Catalog DDL + notebooks (setup, probe, pipeline, prices, source test) |
| [databricks.yml](databricks.yml) · [resources/](resources/) | Databricks Asset Bundle: the three jobs |
| [web/](web/) | Next.js website (next milestone); UI reference in [docs/ui/prototype.html](docs/ui/prototype.html) |
| [docs/](docs/) | Architecture, free-tier setup, design system, implementation plan |

## Quick start (laptop, mock mode, no keys needed)

```bash
cd backend
uv sync --python 3.12
uv run catalyst run --force          # one pipeline run on simulated pages → alerts in data/local/catalyst.sqlite
uv run catalyst alerts               # list them
uv run catalyst sources              # all sources and whether they're due
uv run catalyst snapshot LT          # pivots S1–S3/R1–R3, 52-week, trend, RSI, circuit
uv run pytest -q                     # tests (mock mode, no network)
```

Modes (`CATALYST_MODE` in `.env`, see [.env.example](.env.example)):
- **mock**: simulated pages in the real formats, deterministic AI. Free and offline.
- **local**: real sources + LM Studio models (Qwen3) on your laptop.
- **live**: Databricks jobs + real sources + Databricks model endpoints (or Claude).

## Databricks (Free Edition)

Step by step in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md#databricks-setup-step-by-step): create a Git folder from this repo → run `databricks/notebooks/00_setup` → `10_pipeline_run`.

## Docs

[aim.md](aim.md) · [PLAN.md](PLAN.md) (roadmap) · [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (detailed tasks + status) · [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/ARCHITECTURE-FREE-TIER.md](docs/ARCHITECTURE-FREE-TIER.md) · [SOURCES.md](SOURCES.md) · [docs/DESIGN.md](docs/DESIGN.md) · [PRINCIPLES.md](PRINCIPLES.md) · [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md)
