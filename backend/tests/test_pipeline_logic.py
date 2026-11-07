from catalyst.config import load_triage_rules, load_watchlist
from catalyst.pipeline.analysis import enforce_citations, same_story, title_tokens
from catalyst.pipeline.matching import CompanyMatcher, dedupe
from catalyst.pipeline.triage import rule_score
from catalyst.schemas import AlertDraft, Evidence, Fact, RawItem, Source

NEWS = Source(id="n", name="n", market="india", parser="rss", trust="news")
OFFICIAL = Source(id="o", name="o", market="india", parser="rss", trust="official")


def item(title: str, summary: str = "", **kw) -> RawItem:
    return RawItem(source_id="t", url=f"https://x/{abs(hash(title))}", title=title, summary=summary, **kw)


def test_whole_word_keywords_no_bank_false_positive():
    rules = load_triage_rules()
    rs = rule_score(item("HDFC Bank shares jump 3% after strong loan growth update"), NEWS, rules)
    assert rs.event_type != "regulatory"  # 'ban' must not match inside 'Bank'


def test_plural_keywords_match():
    rules = load_triage_rules()
    rs = rule_score(item("BEL receives orders worth ₹1,240 crore"), NEWS, rules)
    assert rs.event_type == "order_win"
    assert "large amount" in rs.reason


def test_routine_filings_score_low():
    rules = load_triage_rules()
    rs = rule_score(item("LT: Closure of trading window"), OFFICIAL, rules)
    assert rs.event_type == "routine" and rs.score < rules["threshold"]


def test_official_and_multi_outlet_boosts():
    rules = load_triage_rules()
    base = rule_score(item("Company wins order"), NEWS, rules).score
    boosted = rule_score(item("Company wins order", related_count=2), OFFICIAL, rules).score
    assert boosted > base


def test_matcher_aliases_and_short_tickers():
    m = CompanyMatcher(load_watchlist())
    assert m.match(item("L&T bags metro order")) == ["larsen-toubro"]
    assert m.match(item("BEL shares hit record high")) == ["bharat-electronics"]
    assert m.match(item("the bel tower rang")) == []  # short tickers only as exact uppercase words
    assert m.match(item("anything", company_hint="Infosys")) == ["infosys"]


def test_dedupe_within_batch_and_against_seen():
    a, b = item("Same headline"), item("Other headline")
    seen = {b.content_hash}
    assert dedupe([a, a, b], seen) == [a]


def test_same_story_overlap():
    assert same_story(
        title_tokens("L&T bags metro order in Chennai"), title_tokens("L&T secures metro order Chennai project")
    )
    assert not same_story(title_tokens("L&T bags metro order"), title_tokens("Gold prices edge higher"))


def test_citations_enforced():
    ev = [Evidence(evidence_id="ev_real", event_id="e", url="https://x", source_id="s")]
    draft = AlertDraft(
        sentiment="positive",
        priority="High",
        headline="h",
        what_happened="w",
        why_it_matters="y",
        risks="r",
        bull_case="b",
        bear_case="b",
        next_steps="n",
        facts=[
            Fact(key="ok", value="1", verification="confirmed", evidence_ids=["ev_real"]),
            Fact(key="made_up", value="2", verification="confirmed", evidence_ids=["ev_fake"]),
        ],
    )
    out = enforce_citations(draft, ev)
    assert out.facts[0].verification == "confirmed"
    assert out.facts[1].evidence_ids == [] and out.facts[1].verification == "unconfirmed"
