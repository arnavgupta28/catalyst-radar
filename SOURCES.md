# Sources — What We Track (and How Users Add More)

> **Update (7 Nov 2026): no TinyFish Agent.** The Agent is paid per step, so Catalyst uses only **direct HTTP**, **TinyFish Fetch** (free to 1,000 URLs/day) and **TinyFish Search** (free to 12,000/day). Where the tables below still say "Agent": NSE filings come from Moneycontrol corporate actions plus TinyFish Fetch on NSE's JSON feed; BSE is disabled; Bloomberg and Reuters headlines come via TinyFish Search; custom sources fall back to Fetch only. The live config is in [config/markets/](config/markets/).

Sources come in **packs per market**. Each pack is a config file, not code. The 🇮🇳 **India pack** (10 sources, below) is the default. The 🇺🇸 **US pack** is a starter set. Users can **add their own sources** on top (see the end of this file).

```
Source = built-in (from a market pack)  or  custom (added by a user)
Scope  = whole market  ·  one company  ·  one exchange (NSE / BSE / NYSE / NASDAQ)
```

We split sources into three trust levels. **Official sources are the truth.** News confirms and adds context. Context sources help explain the numbers.

| Trust level | Meaning | How we use it |
|---|---|---|
| 🟩 **Official** | The company or regulator said it | Can trigger an alert on its own |
| 🟨 **News** | A journalist reported it | Confirms an official item, or triggers a *"needs verification"* alert |
| 🟦 **Context** | Financial data / background | Explains why the news matters (e.g. "₹500 cr = 12% of revenue") |

## 🇮🇳 India pack — the 10 built-in sources

> **NSE vs BSE per stock:** most large Indian companies list on both exchanges and file the same announcement on each. The user picks **NSE**, **BSE**, or **Both** per stock. "Both" also gives us a free cross-check and a fallback if one site is down.

| # | Website | Trust | What we look for | How we read it (TinyFish) | Check every |
|---|---|---|---|---|---|
| 1 | **NSE – Corporate Announcements**<br>`nseindia.com/companies-listing/corporate-filings-announcements` | 🟩 | Order wins, results, board meetings, management changes, acquisitions. Attached PDFs. | **Agent** (stealth browser) — the site blocks simple bots and needs cookies | 5 min |
| 2 | **BSE – Corporate Announcements**<br>`bseindia.com/corporates/ann.html` | 🟩 | Same as NSE; often has filings NSE shows later, plus PDF attachments | **Agent** (lite) to list, **Fetch** for the PDF | 5 min |
| 3 | **SEBI – Orders & Press Releases**<br>`sebi.gov.in` | 🟩 | Penalties, bans, investigations, settlement orders naming our companies | **Fetch** (simple pages) | 30 min |
| 4 | **Zerodha Pulse**<br>`pulse.zerodha.com` | 🟨 | One page aggregating the last 24 h of Indian business news (ET, Business Standard, NDTV Profit, Hindu BusinessLine…) with trending tags. ⭐ **Our main news feed** ([details below](#zerodha-pulse--our-main-news-feed)). | **Direct HTTP** from Databricks, **TinyFish Fetch** as fallback | 5 min |
| 5 | **Moneycontrol – Markets**<br>`moneycontrol.com/news/business/markets/` + market-data pages | 🟨 + 🟦 | ⭐ Market news **plus market data**: price/volume shockers, corporate actions, bulk/block deals, earnings calendar, FII/DII ([details below](#moneycontrol--markets-section-news--market-data)) | **Fetch** (HTML + embedded JSON) | 15 min – daily |
| 6 | **Economic Times – Markets**<br>`economictimes.indiatimes.com/markets/stocks/news` | 🟨 | Deal and order news, sector stories | **Fetch** | 15 min |
| 7 | **Business Standard – Markets**<br>`business-standard.com/markets` | 🟨 | Deeper company and policy coverage | **Fetch** (headline + summary; some articles paywalled) | 15 min |
| 8 | **Mint – Markets**<br>`livemint.com/market` | 🟨 | Company and market news | **Fetch** | 15 min |
| 9 | **Bloomberg – Asia / India**<br>`bloomberg.com/asia` | 🟨 | Global angle: large deals, foreign investor moves, global peers. **Headlines only** (paywalled). | **Agent** (stealth) — search company name, read headline + teaser | 30 min |
| 10 | **Screener.in – Company page**<br>`screener.in/company/<SYMBOL>/` | 🟦 | Revenue, profit, margins, order book, past results; used to size an event | **Fetch** with CSS selectors | Once a day |

**Bonus (per company, not counted):** each company's **Investor Relations page** (press releases, presentations), read with **Fetch**.

## Zerodha Pulse — our main news feed

One page, ~170 stories from the last 24 hours, across all major Indian business outlets. **One fetch covers what would otherwise take 6+ site visits**, so it's checked most often, and the individual news sites become backups and deep-read targets.

**Page structure** (checked 7 Nov 2026):

| Element | Selector | What we take |
|---|---|---|
| Story | `li.box.item` (id `item-<n>`) | One raw item; `<n>` is a stable id, perfect for de-dup |
| Headline + link | `h2.title > a` (`href`, `data-id`) | Title and the **original article URL** (evidence link) |
| Summary | `div.desc` | 1–2 sentence teaser for triage |
| Exact time | `span.date[title]`, e.g. `06:33 PM, 07 Nov 2026` | Published time (IST); ignore the "1.5 hours ago" text |
| Outlet | `span.feed`, e.g. `— NDTV Business` | Source name |
| Related coverage | `ul.similar` inside a story | **Same story from other outlets**: a free cross-check for the Verifier |

**How we use it**
1. **Fetch every 5 min** (7 am–11 pm IST). Direct HTTP from the Databricks job with a normal browser User-Agent; if that fails, fall back to TinyFish Fetch with `include_selectors: ["li.box.item"]`.
2. **Parse** with the selectors above → `raw_items` (key = Pulse item id + URL hash).
3. **Match to our watchlist** using company names, aliases and symbols (e.g. "L&T", "Larsen", "LT").
4. **Count coverage:** a story with several `ul.similar` entries is widely reported, which raises its materiality score.
5. **Go deeper only on matches:** open the original article (TinyFish Fetch) and look for the official NSE/BSE filing (TinyFish Agent).
6. **Be polite:** one request per run, cache with ETag, and never hammer the page.

## Moneycontrol — Markets section (news + market data)

Checked 7 Nov 2026. The **Markets** menu gives us two kinds of data: **news feeds** (by category filter) and **market-data pages** (stats, actions, deals, earnings). All are public pages; the data pages embed their data as JSON (`<script id="__NEXT_DATA__">`), which is sturdier to parse than HTML.

### A. News feeds (category filters)

| Filter | URL | What's there | Use |
|---|---|---|---|
| **Markets** | `/news/business/markets/` | Market + company news (25 per page, `page-2/`…) | Company news → triage |
| **Stocks** | `/news/business/stocks/` | Brokerage calls, e.g. *"Neutral Dabur; target of Rs 425: Motilal Oswal"* | "Brokerage view changed" as **third-party opinion**, never our call |
| **Earnings** | `/news/business/earnings/` | Results stories | Results catalysts |
| **IPO** | `/news/business/ipo/` | IPO news | v2 |
| Companies · Economy · Commodities | `/news/business/companies/` … | Wider context | Optional |

**List structure:** `ul#cagetory > li[id^="newslist-"]` → `a[href][title]` (link + headline), `h2` (headline), `p` (summary). ⚠️ **No timestamp in the list**: take the time from the article page or from the matching Pulse story.

### B. Market-data pages (Markets menu)

| Page | URL | JSON path (in `__NEXT_DATA__` → `props.pageProps`) | Filters available | How Catalyst uses it | Check |
|---|---|---|---|---|---|
| **Price Shockers** / **Volume Shockers** | `/stocks/market-stats/price-shockers-nse/` (also `-bse`, `volume-shockers-nse`) | `marketStatsData` | Exchange NSE/BSE; tabs: Top Gainers, Top Losers, 52 Wk High/Low, Only Buyers/Sellers, Price/Volume Shockers, Most Active | 🚨 **"Unusual move" trigger**: a watchlist stock moving sharply with no news → go find out why (Pulse, NSE filing) | 15 min in market hours |
| Top Gainers / Losers, 52-wk High/Low | `/stocks/market-stats/top-gainers-nse/` … | `marketStatsData` | same | Context ("hit a 52-week high today") | 30 min |
| **Corporate Action** | `/markets/corporate-action/` | `data.filteredList[<date>]` → `stockName, announcementDate, eventType, purpose, attachment_url` | Event types: **Board Meeting, Announcement, AGM-EGM** (plus dividend / bonus / split tabs) | 📅 **Upcoming events calendar** ("Board meeting on results next week") | Daily |
| **Deals** | `/markets/stock-deals/` | `data.topWeeklyDealsData`, deals list | Deal type **Bulk, Block, Insider, SAST** · period 1W/1M/3M/6M · NSE/BSE | 💰 **Big-money moves** in watchlist stocks (insider buying, large block trades) | Daily (evening) |
| **Earnings** | `/markets/earnings/` | `earningsDashboardData.resCalData` (date, stock, quarter, time), results, estimates | Date strip | 📅 "Results today/this week"; later, surprise vs estimates | Daily |
| **FII & DII Activity** | `/markets/fii-dii-data/` | `FiiDiiData.fiiDiiData` (date, FII/DII cash, F&O) | Last 30 days | 🌐 Market mood card on Overview | Daily |

### How we read Moneycontrol
- **TinyFish Fetch** (`format: html`) for each page, then parse the embedded JSON (data pages) or the list selectors (news). Direct HTTP from Databricks if a quick test shows it's reachable.
- **Only public pages.** The page config shows internal API URLs (`api.moneycontrol.com/swiftapi/...`); we **don't** call those undocumented APIs directly.
- **Polite:** at most one request per page per check, at least 1 s apart, cached with ETag.
- **New event types** from this source: `unusual_move`, `corporate_action`, `bulk_block_deal`, `insider_trade`, `results_scheduled`, `brokerage_view` (third-party opinion).

## Not scraped — official APIs instead

> **Free-tier choice:** Angel One SmartAPI → Upstox → yfinance (India) and Finnhub → Alpaca → Twelve Data (US). Kite and Groww stay as paid upgrades. Details: [docs/ARCHITECTURE-FREE-TIER.md](docs/ARCHITECTURE-FREE-TIER.md#3-price-apis-with-free-daily-limits).

| Data | Source | Why |
|---|---|---|
| Live price, day change, OHLC | **Zerodha Kite Connect** (`/quote`, `/quote/ltp`, up to 1,000 symbols per call) | Official, reliable, allowed |
| Backup price source | **Groww Trade API** (`growwapi` Python SDK; live data 10 req/s, 300/min) | Fallback if Kite is down |
| Price history (for "how did the stock react last time?") | Kite historical candles / Groww historical (from 2020) | Same |

## What we learned from each platform

- **TinyFish**: Five tools. **Fetch** (free up to 1,000 URLs/day, 10 URLs per call, returns clean markdown, supports caching via `ttl` and ETags). **Search** (free daily allowance). **Agent** (paid per run; natural-language `goal` + `output_schema` for structured JSON; `lite` or `stealth` browser; live SSE progress stream and a **watch-live `streaming_url`**). **Research** (multi-source report). **Browser** (raw remote browser). → *We use Fetch for most pages and the Agent only for hard pages.*
- **Zerodha (Kite Connect)**: REST + WebSocket APIs for quotes, historical data, and orders. Login needs a daily handshake with `api_key` + `api_secret` on a backend (never in the browser). Paid subscription for market data.
- **Zerodha Pulse**: Not an API, just a fast news aggregator page with a reverse-chronological list, exact timestamps, source names and related-coverage groups. Perfect as a cheap "something happened" signal; we then go to the original site.
- **Groww Trade API**: Python SDK `growwapi`, API key + secret or TOTP login, live quotes/LTP/OHLC, WebSocket feed (up to 1,000 subscriptions), historical candles. ~₹499/month subscription.
- **Bloomberg**: Real data access (Terminal Desktop API, Server API, B-PIPE via `blpapi`) needs an expensive licence, so it's **out of scope**. We only read public bloomberg.com headlines, never paywalled content.

## Starting watchlist (5 Indian companies; editable)

Chosen because each regularly produces a different kind of catalyst:

| Company | Symbol | Typical catalyst |
|---|---|---|
| Larsen & Toubro | `LT` | Large order wins (perfect for the hero alert) |
| Bharat Electronics | `BEL` | Defence orders |
| Infosys | `INFY` | Results, guidance changes, large deals |
| HDFC Bank | `HDFCBANK` | RBI / regulatory news, results |
| Reliance Industries | `RELIANCE` | Acquisitions, new businesses, global coverage |

## 🇺🇸 US pack — starter set (should-have)

| # | Website | Trust | What we look for | How we read it |
|---|---|---|---|---|
| 1 | **SEC EDGAR** (`sec.gov/edgar`, JSON at `data.sec.gov`) | 🟩 | 8-K (material events), 10-Q/10-K, Form 4 insider trades. The US equivalent of NSE/BSE filings. | **Fetch** (public JSON; needs a descriptive User-Agent) |
| 2 | **Company IR / press releases** | 🟩 | Earnings releases, product launches | **Fetch** |
| 3 | **Reuters – Markets** | 🟨 | Breaking company news | **Fetch** / **Agent** |
| 4 | **CNBC / MarketWatch** | 🟨 | Market and company coverage | **Fetch** |
| 5 | **Bloomberg (headlines)** | 🟨 | Same rule as India: public headlines only | **Agent** (stealth) |

US prices come from a US market-data API (e.g. Finnhub or Alpaca free tier), behind the same `PriceProvider` interface as Kite/Groww.

## Market settings

| Market | Exchanges | Currency | Trading hours (local) | Price provider | Source pack |
|---|---|---|---|---|---|
| 🇮🇳 India | NSE, BSE | ₹ INR | 09:15–15:30 IST | Kite Connect → Groww | `config/markets/india.yaml` |
| 🇺🇸 US | NYSE, NASDAQ | $ USD | 09:30–16:00 ET | Finnhub / Alpaca | `config/markets/us.yaml` |

Adding a new market (e.g. 🇬🇧 UK) means adding one YAML file and one price-provider class. Nothing else changes.

## Adding your own source (custom sources)

**What the user sees:** Sources screen → **+ Add source**

1. **Paste a link**, e.g. `https://www.tatasteel.com/media/newsroom/`
2. **Choose the scope:** whole market, or just one stock (e.g. "only for TATASTEEL")
3. **Optional hint:** "Look for order wins and plant expansions" (becomes the agent's goal)
4. Click **Test**. Catalyst reads the page and shows the first 5 items it found:
   - Simple page → TinyFish **Fetch** (fast, free)
   - Fetch finds nothing useful → TinyFish **Agent** with the hint as its goal (slower, live preview shown)
5. Set the name and **check frequency** (15 min / 1 h / daily) → **Save**. The source appears with a 🟪 *Custom · Unverified* badge.

**Built-in protections**

| Rule | Why |
|---|---|
| Only `https://` public pages; no login pages, no file downloads above 20 MB | Safety, legality |
| Custom sources start as **Unverified**: they can raise *"needs verification"* alerts but never a High-priority alert alone | Stops junk sites from creating false alarms |
| Minimum check interval of 15 min; max 20 custom sources per user | Cost and politeness |
| A source that fails 5 times in a row is paused, and the user is told | Reliability |
| Two users adding the same URL share **one** watcher | Scalability |

**Source config shape** (same for built-in YAML and user-added rows in the DB):

```yaml
- id: nse-announcements
  name: NSE – Corporate Announcements
  market: india
  exchange: NSE            # optional: NSE | BSE | NYSE | NASDAQ
  scope: market            # market | company
  company: null            # e.g. LT when scope = company
  url: https://www.nseindia.com/companies-listing/corporate-filings-announcements
  trust: official          # official | news | context | unverified
  method: agent            # fetch | agent | auto (try fetch, fall back to agent)
  browser_profile: stealth
  goal: "List today's announcements: company, subject, time, PDF link"
  interval: 5m
  enabled: true
  builtin: true
```

## Rules we follow

- Read only **public** pages; never bypass logins or paywalls.
- Respect each site's load: low polling rates, caching (`ttl`, ETags), no hammering.
- Always **link back** to the original source; store only short extracts.
- ⚠️ TinyFish built-in proxies don't offer India yet; if NSE blocks foreign IPs we use the `custom` proxy option or fall back to BSE.
