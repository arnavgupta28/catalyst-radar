# Implementation Plan (detailed)

The task-level companion to the roadmap in [PLAN.md](../PLAN.md). Updated as we build.

**Legend:** ✅ done · 🔜 next · ⏳ later · 👤 needs you

---

## 1. Decisions so far

| # | Decision | Chosen | Why |
|---|---|---|---|
| 1 | Code hosting | **Public GitHub repo** `arnavgupta28/catalyst-radar` | Unlimited Actions minutes; Databricks Git folder clones without a token; no secrets in code |
| 2 | Unity Catalog layout | **Catalog `catalyst`** (bronze/silver/gold/ops); auto-fallback to `workspace.catalyst_*` | Clean names; setup notebook handles Free Edition refusing a new catalog |
| 3 | App database | **Delta first**, Lakebase when the website goes live | Fewer moving parts now; SQL store code is Postgres-compatible for later |
| 4 | Python tooling | **uv + Python 3.12** | Fast, lockfile, matches Databricks serverless |
| 5 | TinyFish | **Search + Fetch only; no Agent** | Agent costs per step ($0.016); Search free to 12,000/day, Fetch free to 1,000 URLs/day |
| 6 | NSE filings (no Agent) | Moneycontrol corporate actions (relays exchange announcements) + **TinyFish Fetch** on NSE's JSON feed; BSE disabled | NSE times out from Databricks; BSE blocks plain requests |
| 7 | Main news feed | **Zerodha Pulse** (direct, TinyFish Fetch fallback) + Moneycontrol market section | One request covers most Indian outlets; Moneycontrol adds market data |
| 8 | Website hosting | **Vercel** | No sleeping on free tier; Next.js native |
| 9 | Local AI | **LM Studio**: Qwen3 1.7B (triage), Qwen3 4B (writer), Qwen3.5 9B (quality) | Free, under 4 GB each |
| 10 | Prices | India: **Angel One** (M3) → yfinance (laptop only); US: **Finnhub** | Free; Yahoo is rate-limited from Databricks |

## 2. What's built (M0 + most of M1)

| Area | Status | Where |
|---|---|---|
| Repo, uv project, lint (ruff), types (mypy), tests (pytest), CI | ✅ | `backend/pyproject.toml`, `.github/workflows/ci.yml` |
| Config: India + US market packs, watchlist (sector, asset class, multi-listing), triage rules | ✅ | `config/` |
| Typed schemas for every step | ✅ | `backend/src/catalyst/schemas.py` |
| Providers behind switches (web: mock/direct/TinyFish/auto · LLM: mock/LM Studio/Databricks/Claude · prices: mock/yfinance/Finnhub) | ✅ | `providers/` |
| Parsers: Pulse, Moneycontrol (news, corporate actions, price/volume shockers, deals, earnings calendar, FII/DII), RSS, NSE JSON, SEC EDGAR, TinyFish Search hits | ✅ checked against real pages | `sources/` |
| Pipeline: de-dup, company matching, rule + LLM triage, same-story merging, evidence collection, alert writing with **citation enforcement** | ✅ | `pipeline/` |
| Analytics (from your input.md): S1–S3 / R1–R3 pivots, 52-week high/low flags, trend arrow, SMA/EMA/RSI, circuit %, 1D/1W/1M returns, sector + asset-class groups with bullish/bearish mood | ✅ | `analytics/` |
| Stores: SQL (SQLite/Postgres) and Delta (Databricks) | ✅ | `store/` |
| CLI: run / sources / probe / snapshot / alerts | ✅ | `cli.py` |
| Mock mode: simulated pages in the real formats; full run → 10 grounded alerts; second run idempotent | ✅ | `mock_data/` |
| Databricks: DDL (schemas, volume, 11 tables, 4 views), notebooks (setup, probe, pipeline, prices, source test), bundle with 3 jobs (paused) | ✅ written · 👤 to run | `databricks/`, `databricks.yml`, `resources/` |

## 3. Databricks setup (step by step)

Workspace: `https://dbc-8de4d59f-c9f5.cloud.databricks.com`

1. **Git folder** 👤: *Workspace → Create → Git folder* → URL `https://github.com/arnavgupta28/catalyst-radar` → Create. (Public repo: no token needed.)
2. **Setup** 👤: open `databricks/notebooks/00_setup` → *Run all* (serverless). It installs the package, creates `catalyst` (or falls back to `workspace.catalyst_*`), runs `databricks/sql/*.sql`, and loads config into `ops` tables. **Note the catalog/prefix it prints.**
3. **Probe** 👤: run `01_probe_outbound`. It tells us which sources work directly and which go through TinyFish Fetch.
4. **Mock run on Databricks** 👤: run `10_pipeline_run` with `mode=mock`, `force=true`, then check:
   ```sql
   SELECT * FROM catalyst.gold.v_feed ORDER BY created_at DESC;
   SELECT * FROM catalyst.ops.v_source_health;
   ```
5. **Databricks CLI** 👤 (needed for secrets and bundle deploy):
   ```bash
   brew trust databricks/tap && brew install databricks
   databricks auth login --host https://dbc-8de4d59f-c9f5.cloud.databricks.com --profile catalyst
   ```
6. **Secrets** 👤:
   ```bash
   databricks secrets create-scope catalyst --profile catalyst
   databricks secrets put-secret catalyst tinyfish_api_key --profile catalyst
   databricks secrets put-secret catalyst finnhub_api_key --profile catalyst
   # after choosing models on the Serving page:
   databricks secrets put-secret catalyst databricks_triage_model --profile catalyst
   databricks secrets put-secret catalyst databricks_writer_model --profile catalyst
   ```
7. **Model endpoints** 👤: open *Serving* and tell me which Foundation Model endpoints Free Edition shows; I'll pick triage/writer models.
8. **Live run**: `10_pipeline_run` with `mode=live`, `force=true`.
9. **Jobs**: `databricks bundle deploy --profile catalyst` (add `--var="catalog=workspace" --var="prefix=catalyst_"` if setup fell back). Jobs are created **paused**; unpause `catalyst-pipeline` once a live run looks good.

## 4. Next tasks

### 🔜 M1b: Website (Next.js, Vercel)
- [ ] Scaffold `web/` (Next.js + TypeScript + Tailwind), port tokens and Kat from `docs/ui/prototype.html`
- [ ] Browser mock mode: simulator driven by the simulation dataset JSON
- [ ] Screens: Overview, Feed, Deep dive, Sources (add source → `catalyst-source-test` job), Markets switcher
- [ ] New input.md views: sector trends, watchlist 1D/1W/1M + bullish/bearish, equities / ETFs / commodities tabs, S1–S3/R1–R3, 52-week alerts, trend arrows, circuit %
- [ ] API routes: read Delta via SQL Statement API (until Lakebase), trigger jobs via Jobs API

### 🔜 Simulation dataset (Excel)
- [ ] Fetch real price history (laptop, Yahoo) + real recent Pulse/Moneycontrol/NSE/SEC items for the watchlist
- [ ] Build `data/simulation/catalyst_simulation.xlsx` (prices_daily, prices_intraday, filings, news, events, timeline) and export JSON for the browser mock

### ⏳ M2: LM Studio
- [ ] Run `CATALYST_MODE=local LLM_PROVIDER=lmstudio uv run catalyst run --force`; tune prompts; compare with mock

### ⏳ M3: Real data
- [ ] Angel One SmartAPI provider (TOTP login) 👤 needs account + API key
- [ ] Test NSE JSON via TinyFish Fetch; keep or drop `nse_announcements`
- [ ] Record live runs as fixtures for replay
- [ ] Price-based alerts: 52-week high/low, near S1/R1, circuit hits, results day reminders

### ⏳ M4–M6
- [ ] Usage dashboard (AI/BI) on `ops.v_usage_today`, `ops.v_source_health`
- [ ] Lakebase + Vercel deploy; daily digest (email/Telegram); US pack polish

## 5. Questions for you (when we get there)
- Which **Databricks model endpoints** appear on your Serving page? (step 7)
- Do you want an **Angel One** account for free real-time Indian prices, or stay on delayed data for now?
- Alerts outside the website: **email, Telegram, or none** for v1?
