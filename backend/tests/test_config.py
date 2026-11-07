from catalyst.config import load_markets, load_sources, load_triage_rules, load_watchlist


def test_markets_and_sources_load():
    markets = load_markets()
    assert {"india", "us"} <= set(markets)
    sources = load_sources(include_disabled=True)
    assert len({s.id for s in sources}) == len(sources)
    for s in sources:
        assert s.market in markets
        assert s.interval_seconds >= 300 or s.interval.endswith(("h", "d"))
        assert s.method in {"direct", "tinyfish_fetch", "tinyfish_search", "auto"}


def test_no_paid_agent_anywhere():
    # TinyFish Agent is paid per step; the design only uses Search + Fetch.
    assert all("agent" not in s.method for s in load_sources(include_disabled=True))


def test_pulse_and_moneycontrol_are_enabled():
    ids = {s.id for s in load_sources()}
    assert "pulse" in ids
    assert {"mc_markets_news", "mc_corporate_action", "mc_price_shockers"} <= ids


def test_watchlist_has_asset_classes_and_sectors():
    companies = load_watchlist()
    assert {c.asset_class for c in companies} == {"equity", "etf", "commodity"}
    assert all(c.sector for c in companies)
    infy = next(c for c in companies if c.id == "infosys")
    assert infy.markets == {"india", "us"}  # dual-listed: NSE/BSE + NYSE ADR


def test_triage_rules_shape():
    rules = load_triage_rules()
    assert 0 < rules["threshold"] < 100
    assert "routine" in rules["event_types"]
