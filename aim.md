# Catalyst Radar — What We're Building

> **In one line:** Catalyst Radar watches the companies you care about, reads the official announcements and news for you, and tells you what changed, why it matters, and where the proof is.

Think of it as a **personal research assistant for the stock market**. You tell it which companies you follow. It keeps an eye on the websites where news about those companies appears. When something important happens, it reads the original document, checks it against other sources, and sends you a short, plain-English note.

You no longer have to open ten websites, read dozens of announcements, or guess whether a headline matters.

> **Why we're building it:** this is a personal project. We're building it **to explore** (web agents, local and hosted LLMs, market data, real-time UIs) and **to use it ourselves** every day to follow our own stocks. No deadline, no competition: we build it properly, one step at a time, and keep it cheap to run.

---

## 1. The problem

**Who:** Us first, and anyone like us: investors who own or follow 5–20 stocks in India (and a few in the US) and don't have time to read every filing.

**Pain:** Information about a listed company is spread across many places:

- **Stock exchanges** (NSE, BSE) — where companies must post official announcements
- **The regulator** (SEBI) — orders, penalties, rule changes
- **News sites** (Economic Times, Moneycontrol, Business Standard, Bloomberg…)
- **The company's own website** — investor presentations, press releases

NSE + BSE alone publish **thousands of announcements a day**. Most are routine paperwork. A normal investor has neither the time to check every source daily nor the background to tell a big announcement from routine filing. Most stock apps show prices and a list of headlines, then leave the hard part — **"so what?"** — to the user.

**Result:** Investors either miss important news or react to headlines without reading the source.

## 2. What the user gets

| # | Feature | What it means for the user |
|---|---------|----------------------------|
| 1 | **Watchlist** | Add the stocks you follow. See the live price (from free market-data APIs) and the latest important events for each. |
| 2 | **Smart alerts** | You don't get every headline, only the ones likely to matter: big orders, results surprises, management changes, regulator action, new products, serious risks. Each alert has a priority (High / Medium / Low). |
| 3 | **"Why it matters"** | The tool reads the original announcement, pulls out the key numbers, and explains in simple language how it could affect sales, costs, profits, or risk. |
| 4 | **Proof, not just AI opinion** | Every important claim links to its source. The alert clearly separates **facts** (what the document says) from **analysis** (what it might mean), and flags anything conflicting or unconfirmed. |
| 5 | **Both sides** | Each alert shows the possible upside, what could go wrong, and what to check next before making a decision. |

## 2a. Make it yours — everything is configurable

The 10 built-in sources are only a starting point. The user stays in control.

| The user can… | How it works |
|---|---|
| **Pick their stocks** | Search and add any stock, e.g. `LT` on NSE or `AAPL` on NASDAQ. Remove or reorder anytime. |
| **Switch between markets** | A market switcher at the top: **🇮🇳 India · 🇺🇸 US · 🌐 All**. Each market has its own currency, trading hours, and sources. |
| **See stocks clearly separated** | Stocks are grouped by market, and every stock shows a flag, exchange badge (NSE / BSE / NYSE / NASDAQ), currency (₹ / $), and whether its market is open or closed right now. |
| **Choose the exchange to watch** | For Indian stocks: watch **NSE**, **BSE**, or **both** (same company, two exchanges). |
| **Turn sources on/off** | Don't trust a site? Switch it off for one stock or for everything. |
| **Add a new source** | Paste a link (e.g. a company's press-release page or a niche industry site), give it a name, and pick the market. Catalyst tests the link, shows a preview of what it found, and starts watching it. |

**From the stock's point of view:** one company can trade in more than one place. Infosys, for example, trades on NSE and BSE in India and as an ADR on NYSE in the US. Catalyst treats this as **one company with several listings**. News about Infosys is found once and shown under every listing, each with its own price and currency.

**Safety rule for user-added sources:** a source the user adds starts as *"unverified"*. It can flag news, but it **cannot on its own** create a High-priority alert. An official source must confirm it first.

## 3. What an alert looks like

*Illustrative example — not a real market alert.*

> **🟢 Catalyst detected: New order win** — *Priority: High*
> **Company:** Example Engineering Ltd (NSE: EXAMPLE)
>
> **What happened**
> The company told the stock exchange it won a ₹500 crore contract, to be completed over 18 months.
> *Source: NSE announcement, 14 Oct 2026, 4:12 PM* 🔗
>
> **Why it may matter**
> ₹500 crore is about 12% of last year's revenue, so it adds meaningful future business. How much it helps depends on profit margin, payment terms, and whether it's delivered on time.
>
> **What could go wrong**
> Delays, a low-margin contract, money tied up while the work is done, or the market may already have expected this order.
>
> **Evidence check**
> ✅ Order value and timeline — confirmed in the exchange filing
> ✅ Also reported by Economic Times and Moneycontrol
> ⚠️ Margin and customer name — not disclosed
>
> **What to check next**
> Compare with the current order book, past revenue, and margins in the next results.
>
> **Bottom line:** Potentially important. Needs more financial checking. This is research, not a buy or sell call.

The point: the tool doesn't just say *"an order was announced."* It explains the announcement **in the context of the business** so the user can decide whether it deserves attention.

## 4. How the user uses it — three screens

A market switcher (**India · US · All**) sits at the top of every screen.

1. **Watchlist** — your companies grouped by market, with live price, exchange badge, and a badge showing how many new important events each has.
2. **Feed** — a single timeline of alerts across all your companies, sorted by importance, each with a summary, label (positive / negative / mixed), time, and source links.
3. **Deep dive** — open any alert to see the original documents, the extracted facts, the bull and bear view, past related events, and **a live view of the AI agents browsing the websites** to gather the evidence.
4. **Sources** — see all sources per market, switch them on/off, and **add your own**.

**Meet Kat** 🐱 — Catalyst's mascot and avatar ([docs/brand/](docs/brand/)). Kat sits in the corner with a radar sweep around it. It spins while agents are working and glows when a new alert lands. Look and feel: [docs/DESIGN.md](docs/DESIGN.md) · clickable prototype: [docs/ui/prototype.html](docs/ui/prototype.html)

## 5. How it works (non-technical)

```
You add stocks  →  Agents watch 10 websites  →  Something new appears
      →  Quick check: "is this important?"  →  Agent opens the original document
      →  Cross-checks with other sources  →  Writes a plain-English alert  →  You
```

**What powers it:**

- **TinyFish** — AI agents that open and read real websites the way a person would (click, scroll, open PDFs, get past pop-ups), even sites with no API. We can **watch the agent browse live**, so it's easy to see (and trust) what it did. Its cheaper *Fetch* tool reads simple pages quickly; the full *Agent* is used only when a site needs clicking around.
- **AI models** — decide what's important, pull out facts, and write the explanation. Free **local models in LM Studio** (Qwen3) while we build; **Claude** when deployed.
- **Market-data APIs** — free official sources for prices: Angel One SmartAPI / Upstox for India, Finnhub for the US. Kite / Groww are optional paid upgrades. We never scrape prices.

Full details: [ARCHITECTURE.md](ARCHITECTURE.md) · Free setup: [docs/ARCHITECTURE-FREE-TIER.md](docs/ARCHITECTURE-FREE-TIER.md) · Sources: [SOURCES.md](SOURCES.md) · Roadmap: [PLAN.md](PLAN.md) · Principles: [PRINCIPLES.md](PRINCIPLES.md)

## 6. Why this instead of a normal stock app?

| Normal stock app | Catalyst Radar |
|---|---|
| Shows prices, charts, and headlines | Reads the actual announcements across many sites |
| Lists headlines | Explains what the news could mean for the business |
| You read and compare sources yourself | It collects and cross-checks sources for you |
| Shows what happened to the price | Shows what changed in the business |
| Interpretation left to you | Gives a structured summary with both sides and open questions |

Catalyst Radar **works alongside** apps like Zerodha Kite or Groww. It does not replace them and does not place trades.

## 7. Scope — what we build, in order

**v1: something we use every day**
1. Editable watchlist (add / remove stocks), starting with **5 Indian companies** and live prices
2. **Market switcher** (India · US · All) with stocks clearly grouped by market and exchange
3. Monitoring of the **10 built-in Indian sources** ([SOURCES.md](SOURCES.md)), with on/off toggles and **NSE / BSE / both** per stock
4. **Add a custom source** (paste link → preview → watch)
5. The full agent run (find → read → cross-check → alert), visible live
6. Evidence-backed alerts we actually trust enough to read daily
7. **Mock mode** that simulates everything, so we can build and test for free

**v2: once v1 is useful**
- US market with a starter pack of 5 sources and a few stocks (AAPL, NVDA, INFY ADR)
- Bull/bear section with counter-arguments
- Alert history per company, with "how did the price react last time?"
- Daily email / Telegram digest
- Deploy on the free tier so it runs without our laptop

**Not planned (on purpose)**
- Buy/sell calls or price targets
- Placing orders or linking a trading account
- Bloomberg Terminal or paid data feeds (public Bloomberg pages only)
- Sign-up, payments, or a public product
- Covering all 5,000+ listed companies

## 8. Quality bar

Even though it's a personal project, we build it like a real product. That's part of the exploration. The full checklist is in [PRINCIPLES.md](PRINCIPLES.md); in short:

| Principle | What it means here |
|---|---|
| **Clear problem** | One job: tell us what changed in our stocks, why it matters, and show the proof. |
| **Deliberate design** | Cheap-first pipeline; official APIs for prices; agents only where no API exists; facts stored separately from analysis ([decision log](ARCHITECTURE.md#8-design-decisions)). |
| **Scales without rewrites** | Work is per company, not per user; sources and markets are config, not code. |
| **Production standards** | Typed code, env config, structured logs, tests, health checks, Docker, no secrets in code. |
| **Clean architecture** | Sources → ingestion → agents → storage → API → UI, with every outside service behind a switch (Live / Local / Mock). |
| **Reliable** | Retries, fallbacks (Fetch → Agent, NSE → BSE, Angel One → Upstox → yfinance), de-duplication, timeouts, and replay mode for working offline. |
| **Cheap to run** | Free tiers + local models while exploring; daily budget guard on anything paid. |

## 9. The promise

> **Know what changed in the companies you follow, why it matters, and what proof supports it — without checking the whole internet yourself.**

The tool helps people **make better-informed research decisions**. It never promises profits and never presents AI opinions as facts.
