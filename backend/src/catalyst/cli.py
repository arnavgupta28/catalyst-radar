"""`catalyst` command line.

catalyst run [--mode mock|local|live] [--force] [--only pulse,mc_markets_news]
catalyst sources            list sources and whether they're due
catalyst probe              check which source hosts are reachable directly from here
catalyst snapshot LT        price analytics (pivots, 52w, trend, RSI, circuit) for a symbol
catalyst alerts             recent alerts from the local store
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from urllib.parse import urlparse

from catalyst.config import get_settings, load_markets, load_sources, load_watchlist


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def cmd_run(args: argparse.Namespace) -> int:
    from catalyst.pipeline.run import run_once
    from catalyst.providers.factory import build_providers
    from catalyst.store.sql import SqlStore

    settings = get_settings()
    store = SqlStore(settings.database_url)
    stats = run_once(
        settings,
        build_providers(settings),
        store,
        force=args.force,
        only=set(args.only.split(",")) if args.only else None,
    )
    print(stats.summary())
    for a in stats.alerts:
        print(f"\n[{a.priority}] {a.sentiment:<8} {a.company_id}: {a.headline}")
        print(f"   why: {a.why_it_matters}")
        print(
            f"   evidence: {len(a.evidence)} source(s) · facts: "
            + ", ".join(f"{f.key}={f.verification}" for f in a.facts)
        )
    for sid, errs in stats.errors.items():
        print(f"\n! {sid}: {errs[0]}" + (f" (+{len(errs) - 1} more)" if len(errs) > 1 else ""))
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    from catalyst.sources.reader import is_due
    from catalyst.store.sql import SqlStore

    markets = load_markets()
    last = SqlStore(get_settings().database_url).last_runs()
    for s in load_sources(include_disabled=True):
        due = is_due(s, markets[s.market], last.get(s.id))
        flag = "off " if not s.enabled else "due " if due else "wait"
        print(f"{flag}  {s.market:<6} {s.id:<28} {s.method:<16} {s.trust:<10} every {s.interval:<5} {s.name}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    import httpx

    settings = get_settings()
    hosts = sorted(
        {
            f"{urlparse(s.url).scheme}://{urlparse(s.url).netloc}/"
            for s in load_sources()
            if s.url and "{" not in urlparse(s.url).netloc
        }
    )
    hosts += [
        "https://api.search.tinyfish.ai/",
        "https://api.fetch.tinyfish.ai/",
        "https://finnhub.io/",
        "https://apiconnect.angelone.in/",
    ]
    with httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=8, follow_redirects=True) as c:
        for h in hosts:
            try:
                r = c.get(h)
                print(f"OK      {r.status_code}  {h}")
            except Exception as exc:  # noqa: BLE001
                print(f"BLOCKED {type(exc).__name__}  {h}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    from catalyst.analytics.indicators import snapshot
    from catalyst.providers.factory import build_price

    settings = get_settings()
    for c in load_watchlist():
        for lst in c.listings:
            if lst.symbol.upper() == args.symbol.upper():
                market = "us" if lst.currency == "USD" else "india"
                provider = build_price(settings.resolved("price_us" if market == "us" else "price_in"), settings)
                candles = provider.history(lst, 365)
                quote = provider.quotes([lst])[0]
                print(
                    json.dumps(
                        {
                            "company": c.name,
                            "exchange": lst.exchange,
                            "provider": provider.name,
                            **snapshot(candles, quote).as_dict(),
                        },
                        indent=2,
                        default=str,
                    )
                )
                return 0
    print(f"{args.symbol} is not in config/watchlist.yaml", file=sys.stderr)
    return 1


def cmd_alerts(args: argparse.Namespace) -> int:
    from catalyst.store.sql import SqlStore

    for a in SqlStore(get_settings().database_url).recent_alerts(args.limit):
        print(f"{a.created_at:%Y-%m-%d %H:%M}  [{a.priority:<6}] {a.company_id:<22} {a.headline}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="catalyst")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--mode", choices=["mock", "local", "live"], help="override CATALYST_MODE")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the pipeline once")
    r.add_argument("--force", action="store_true", help="run every source, even if not due")
    r.add_argument("--only", help="comma-separated source ids")
    sub.add_parser("sources", help="list sources")
    sub.add_parser("probe", help="check direct reachability of source hosts")
    s = sub.add_parser("snapshot", help="price analytics for a symbol")
    s.add_argument("symbol")
    a = sub.add_parser("alerts", help="recent alerts")
    a.add_argument("--limit", type=int, default=20)
    args = p.parse_args(argv)
    if args.mode:
        os.environ["CATALYST_MODE"] = args.mode
        get_settings.cache_clear()
    _setup_logging(args.verbose)
    handlers = {
        "run": cmd_run,
        "sources": cmd_sources,
        "probe": cmd_probe,
        "snapshot": cmd_snapshot,
        "alerts": cmd_alerts,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
