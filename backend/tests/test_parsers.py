from catalyst.sources import feeds, moneycontrol, pulse


def test_pulse_parses_items_time_outlet_and_related(page):
    items = pulse.parse_pulse(page("pulse.html"))
    assert len(items) == 6
    lt = items[0]
    assert lt.title.startswith("L&T bags")
    assert lt.outlet == "Business Standard"
    assert lt.published_at is not None and lt.published_at.tzinfo is not None
    assert lt.related_count == 2
    assert lt.payload["related_outlets"] == ["Economic Times", "Hindu BusinessLine"]
    assert "#" not in lt.url  # tracking fragment stripped
    assert lt.payload["pulse_id"] == "900001"


def test_pulse_related_items_are_not_top_level(page):
    titles = [i.title for i in pulse.parse_pulse(page("pulse.html"))]
    assert not any("Hindu BusinessLine" in t or "steps down" in t for t in titles)


def test_moneycontrol_news_list(page):
    items = moneycontrol.parse_news_list(page("mc_news_list.html"), "mc", tag="x")
    assert [i.title for i in items][1] == "Neutral Infosys; target of Rs 1650: Motilal Oswal"
    assert all(i.tag == "x" and i.outlet == "Moneycontrol" for i in items)


def test_moneycontrol_corporate_action(page):
    items = moneycontrol.parse_corporate_action(page("mc_corporate_action.html"), "mc_ca")
    assert len(items) == 3
    infy = next(i for i in items if i.company_hint == "Infosys")
    assert "buyback" in infy.title.lower()
    assert infy.url.endswith(".pdf")
    assert infy.published_at is not None


def test_moneycontrol_market_stats_deals_earnings_fii(page):
    stats = moneycontrol.parse_market_stats(page("mc_market_stats.html"), "mc_vs")
    assert stats[0].company_hint == "BEL" and "volume shockers" in stats[0].title
    deals = moneycontrol.parse_deals(page("mc_deals.html"), "mc_d")
    assert "block buy" in deals[0].title and deals[0].tag == "bulk_block_deal"
    earn = moneycontrol.parse_earnings_calendar(page("mc_earnings_calendar.html"), "mc_e")
    assert earn[0].tag == "results_scheduled" and "HDFC Bank" in earn[0].title
    fii = moneycontrol.parse_fii_dii(page("mc_fii_dii.html"), "mc_f")
    assert len(fii) == 1 and "FII" in fii[0].title


def test_rss_nse_sec(page):
    rss = feeds.parse_rss(page("rss.xml"), "rss")
    assert len(rss) == 3 and rss[0].url.startswith("https://") and rss[0].published_at is not None
    nse = feeds.parse_nse_announcements(page("nse_announcements.json"), "nse", "LT")
    assert nse[0].company_hint == "LT" and nse[0].published_at is not None
    sec = feeds.parse_sec_submissions(page("sec_submissions.json"), "sec", "AAPL")
    assert [i.payload["form"] for i in sec] == ["8-K", "10-Q"]  # Form 4 skipped
    assert sec[0].company_hint == "NVDA"  # filer's own ticker wins over the listing we asked about


def test_groww_market(page):
    from catalyst.sources import groww

    items = groww.parse_groww_market(page("groww_market.html"), "groww_top_gainers")
    bel, fin = items
    assert bel.company_hint == "BEL" and "top gainers" in bel.title and "+4.80%" in bel.title
    assert bel.payload["change_pct"] == 4.8 and bel.tag == "unusual_move"
    assert "Results yesterday" in fin.title  # Groww's own tag is kept
