# Catalyst Radar — Roadmap

A personal project to **explore** and to **use daily**. No deadline: each milestone ends with something that works, and we only move on when it's useful.

**Approach:** **mock-first**. Build the whole app against simulated data (free, offline, fast), then swap in real services one at a time: local AI, real prices, real websites, then deploy.

> Task-level status and Databricks steps: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). **Status:** M0 done, M1 backend done (website next).

| # | Milestone | Ends with | Cost |
|---|---|---|---|
| M0 | Setup | Repo, config, tooling, simulation dataset | ₹0 |
| M1 | Mock app | Full UI + pipeline running on simulated data | ₹0 |
| M2 | Local AI | Pipeline thinking with LM Studio (Qwen3) | ₹0 |
| M3 | Real data | Real prices + real filings/news via TinyFish | ₹0 (Fetch) + a little Agent |
| M4 | Daily driver | Trustworthy alerts we read every day | Small |
| M5 | Deploy | Databricks Free Edition jobs + Vercel website, without our laptop | Free + small TinyFish/LLM spend |
| M6 | Expand | US market, digests, history, tuning | — |

---

## M0 — Setup

- [ ] Repo skeleton from [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md); `docker-compose.yml` with Postgres + Redis
- [ ] `.env.example`, `ruff`, `mypy`, `pytest`, pre-commit
- [ ] `config/markets/india.yaml` (10 sources) + `us.yaml` (starter pack); loader that upserts them into the DB
- [ ] Seed the 5 starting companies (LT, BEL, INFY, HDFCBANK, RELIANCE) as company + NSE/BSE listings
- [ ] **Simulation dataset (Excel):** real price history + real recent filings/news for our stocks, used to drive mock mode (exported to JSON for the browser simulator)
- [ ] Databricks CLI profile for the workspace; check LinkedIn verification + which model endpoints exist
- [ ] UI reference: [docs/ui/prototype.html](docs/ui/prototype.html) + [docs/DESIGN.md](docs/DESIGN.md)

## M1 — Mock app (everything simulated)

1. **Provider interfaces** with mock implementations: `WebReader`, `PriceProvider`, `LLM` ([free-tier doc §2](docs/ARCHITECTURE-FREE-TIER.md#2-three-ways-to-run-it))
2. **Mock simulator:** replays prices from the dataset and creates catalysts from real past events at realistic times
3. **Pipeline** end to end: Watch → De-dup → Triage → Read → Verify → Analyse → Publish
4. **API:** watchlist, alerts, sources, markets, `/api/stream` (SSE), `/api/tick`, `/health`
5. **Web app:** port the prototype (market switcher, watchlist, feed, deep dive, sources, add stock / add source, Kat)
6. **Tests** on fixtures: de-dup, triage rules, alert schema, citation check

**Done when:** we can leave it running and watch believable alerts flow in, for free.

## M2 — Local AI (LM Studio)

- [ ] LM Studio server on `localhost:1234` with **Qwen3 1.7B** (triage) and **Qwen3 4B** (extract + write); **Qwen3.5 9B** for higher-quality alerts
- [ ] `OpenAICompatibleLLM` provider with JSON-schema structured output
- [ ] Compare local answers vs mock on the same events; tune prompts (`pipeline/prompts/`)

**Done when:** alerts are written by a real model and always match the schema.

## M3 — Real data

- [ ] Prices: **Angel One SmartAPI** (India) → Upstox → yfinance; **Finnhub** (US); cache + budget guard
- [ ] Websites: TinyFish **Fetch** for simple sources; **Agent** for NSE (BSE falls back to Agent too, since it blocks plain requests)
- [ ] **Verifier** with TinyFish Search + Fetch
- [ ] **Record → replay:** save real runs as fixtures so mock mode gets more realistic over time
- [ ] Live agent view in Deep dive (TinyFish `streaming_url`)

**Done when:** a real filing on NSE becomes an alert in our feed within minutes.

## M4 — Daily driver

- [ ] Tune triage so the feed is short and worth reading (track false alarms / misses)
- [ ] Reliability pass: retries, circuit breakers, fallbacks, timeouts
- [ ] Usage card: daily API usage vs free limits
- [ ] Use it for 2 weeks; keep a notes file of what's annoying and fix the top items

**Done when:** we open it instead of checking news sites.

## M5 — Deploy (free tier)

- [ ] **Databricks Free Edition** ([free-tier architecture](docs/ARCHITECTURE-FREE-TIER.md)): LinkedIn verification → outbound test job; Unity Catalog (`bronze/silver/gold`); Lakebase (`live`, `mock`); secret scope
- [ ] `databricks bundle deploy` → jobs `catalyst-pipeline`, `catalyst-prices`, `catalyst-source-test`
- [ ] LLM in prod: Databricks Foundation Model endpoints (or Claude if better); MLflow tracing on
- [ ] **Vercel** website: Next.js pages + API routes reading Lakebase; "Scan now" → Jobs API
- [ ] Mock mode in the browser + `/compare` (Live | Mock); Sentry + UptimeRobot; GitHub Actions CI

**Done when:** it runs 24/7 without our laptop.

## M6 — Expand (pick what's most useful)

- US market pack · bull/bear polish · alert history + price reaction · daily email/Telegram digest · more custom sources · semantic de-dup with embeddings

---

## What we want to learn

| Area | Questions to explore |
|---|---|
| Web agents | When is Fetch enough and when do we need a full Agent? How reliable is TinyFish on NSE/BSE? |
| LLMs | How close do small local models (Qwen3 1.7B / 4B) get to Claude on triage and extraction? |
| Grounding | Does forcing evidence citations really stop made-up claims? |
| Market data | Which free APIs are reliable day to day, and what limits do we actually hit? |
| Real-time UI | SSE + animations: how smooth can live updates feel? |
| Running cost | What does it cost per month to follow 10–20 stocks properly? |

## Design FAQ (decisions we may forget why we made)

| Question | Answer |
|---|---|
| Why not just scrape with BeautifulSoup? | NSE blocks bots and pages change. TinyFish agents follow a plain-English goal, so small layout changes don't break them. We still use cheap Fetch wherever a page is simple. |
| How do we stop AI hallucinations? | Facts are pulled from the filing with a fixed schema. The Analyst must cite an evidence id for every claim, and uncited claims are rejected. Facts and opinions are stored and shown separately. |
| What does it cost to run? | Most calls are free (Fetch, rules, local models). Paid agent runs and Claude run only on roughly 1–5% of items. |
| What if a source goes down? | Retries with back-off, a circuit breaker per source, fallbacks (NSE→BSE, Fetch→Agent, Angel One→Upstox→yfinance), and replay mode. |
| Can we add our own sources or markets? | Yes. Paste a link, we test it with Fetch, then Agent, show a preview, and watch it. User sources start *Unverified*. A new market is one YAML pack + one price provider. |
| Same company on several exchanges? | Company ≠ listing. Infosys is one company with NSE, BSE and NYSE listings: news is found once, prices are shown per listing in its own currency. |
| Is this legal? | Public pages only, polite polling, short excerpts with links back, no buy/sell advice. |

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| NSE blocks non-India IPs (TinyFish proxies don't list India) | BSE fallback; TinyFish `custom` proxy; fixtures |
| Free API limits change or a provider breaks | Provider interface + fallback chain; budget guard; mock mode |
| Agent runs are slow (30–90 s) | Run in the background; cap with `max_steps`; show the live view |
| Daily login tokens (Upstox, Kite) | Prefer Angel One (TOTP auto-login); fall back to yfinance |
| Small local models get things wrong | Schema validation + citation check; use Qwen3.5 9B or Claude for final alerts |
| Feed becomes noisy | Tune triage thresholds; track false alarms in M4 |

## Definition of done (v1)

- [ ] Add stock → see price → scan → live agent view → alert with sources → deep dive
- [ ] Switch India / US / All; stocks clearly grouped by market and exchange
- [ ] Add a custom source and see it in the Sources list
- [ ] Works fully offline in mock mode
- [ ] `docker-compose up` starts everything; `pytest` passes; `/health` is green
- [ ] We've used it daily for 2 weeks and still want to
