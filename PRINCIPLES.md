# Catalyst Radar — Principles

A personal project to **explore** and to **use daily**. Nobody grades it, but we hold it to a real-product bar, because building it properly is part of the point.

## 1. Engineering principles

| # | Principle | What "good" looks like here | Where it lives |
|---|---|---|---|
| 1 | **Clear problem** | One job: tell us what changed in our stocks, why it matters, and show the proof | [aim.md §1](aim.md#1-the-problem) |
| 2 | **Deliberate design** | Every choice has a reason and a trade-off written down | [ARCHITECTURE.md §8](ARCHITECTURE.md#8-design-decisions) |
| 3 | **Scales without rewrites** | Work per company, not per user; sources and markets are config, not code | [ARCHITECTURE.md §7](ARCHITECTURE.md#7-scalability--how-it-grows) |
| 4 | **Solid implementation** | Multi-step pipeline with schema-validated JSON and evidence citations | `backend/app/pipeline/` |
| 5 | **Right scope** | v1 / v2 / not planned, and we stick to it | [aim.md §7](aim.md#7-scope--what-we-build-in-order) |
| 6 | **Production standards** | Typed code, env config, structured logs, tests on fixtures, `/health`, no secrets in code | [ARCHITECTURE.md §9](ARCHITECTURE.md#9-production-standards) |
| 7 | **Understand every part** | We can explain why each piece exists (Fetch vs Agent, hashing, citations, provider switch) | [PLAN.md → Design FAQ](PLAN.md#design-faq-decisions-we-may-forget-why-we-made) |
| 8 | **Clean architecture** | Clear layers; every outside service behind a switch (Live / Local / Mock) | [architecture.svg](docs/architecture.svg) · [free tier](docs/ARCHITECTURE-FREE-TIER.md) |
| 9 | **Complete flows** | Add stock → price → scan → alert with sources → deep dive, all working | [PLAN.md → Definition of done](PLAN.md#definition-of-done-v1) |
| 10 | **Reliable** | Retries, circuit breakers, fallbacks, budget guard, offline mock mode | [ARCHITECTURE.md §6](ARCHITECTURE.md#6-reliability--what-happens-when-things-break) |
| 11 | **Cheap to run** | Free tiers + local models first; daily caps on anything paid | [free-tier doc](docs/ARCHITECTURE-FREE-TIER.md) |

## 2. Rules we follow

| Rule | Why |
|---|---|
| **No buy/sell calls or price targets**; every alert says *research, not investment advice* | Keeps us honest and away from SEBI research-analyst rules |
| **Public pages only**; never bypass logins or paywalls (Bloomberg = headlines only) | Legal and ToS-safe |
| **Polite fetching**: low polling rates, caching, at least 1 s between requests, generic but honest User-Agent | Don't overload sites; avoid getting blocked |
| **Short excerpts + link back** to the original | Copyright-friendly, and it's our evidence feature |
| **Label simulated data clearly** in mock mode | Never mistake a simulated alert for real news |
| **Secrets in env vars / secret scopes only**; nothing committed | Basic hygiene |
| **No personal data sent to third parties** (no emails in headers, URLs or payloads) | Privacy |
| User-added sources start **Unverified** | Junk sources can't create high-priority alerts |
| Stay **within free-tier fair use** (e.g. Databricks Free Edition quotas) | Don't get the workspace shut off |
