"""End to end in mock mode: real pipeline code, simulated pages, deterministic LLM, SQLite store."""

from catalyst.pipeline.run import run_once
from catalyst.store.sql import SqlStore


def test_full_mock_run_produces_grounded_alerts(mock_settings, providers):
    store = SqlStore(mock_settings.database_url)
    stats = run_once(mock_settings, providers, store, force=True)
    assert not stats.errors, stats.errors
    assert stats.new_items > 20
    companies = {a.company_id for a in stats.alerts}
    assert {"larsen-toubro", "bharat-electronics", "infosys", "reliance-industries", "nvidia"} <= companies
    for a in stats.alerts:
        known = {e.evidence_id for e in a.evidence}
        assert a.evidence, a.headline
        assert all(set(f.evidence_ids) <= known for f in a.facts)
        assert a.mode == "mock" and a.disclaimer


def test_same_story_from_many_sources_becomes_one_alert(mock_settings, providers):
    stats = run_once(mock_settings, providers, SqlStore(mock_settings.database_url), force=True)
    lt_orders = [a for a in stats.alerts if a.company_id == "larsen-toubro" and "order" in a.headline.lower()]
    assert len(lt_orders) == 1
    assert len(lt_orders[0].evidence) >= 3  # NSE filing + Pulse (+ related) + Moneycontrol


def test_noise_is_filtered(mock_settings, providers):
    stats = run_once(mock_settings, providers, SqlStore(mock_settings.database_url), force=True)
    heads = " ".join(a.headline for a in stats.alerts).lower()
    assert "gold prices" not in heads and "target of rs" not in heads and "sensex" not in heads


def test_second_run_is_idempotent(mock_settings, providers):
    store = SqlStore(mock_settings.database_url)
    run_once(mock_settings, providers, store, force=True)
    again = run_once(mock_settings, providers, store, force=True)
    assert again.new_items == 0 and not again.alerts
    assert len(store.recent_alerts()) >= 8


def test_sources_respect_intervals(mock_settings, providers):
    store = SqlStore(mock_settings.database_url)
    run_once(mock_settings, providers, store, force=True)
    nothing_due = run_once(mock_settings, providers, store)  # immediately after: nothing is due yet
    assert nothing_due.sources_run == []
