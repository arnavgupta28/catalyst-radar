"""Groww market pages: top gainers / top losers / 52-week high / 52-week low.

Public Next.js pages; the list is embedded as JSON (checked 8 Nov 2026):
  props.pageProps.stocks[]          companyName, nseScriptCode, bseScriptCode, isin, ltp, close (prev close),
                                    yearHigh, yearLow, marketCap, tag (e.g. "Results yesterday")
  props.pageProps.index             e.g. GIDXNIFTYTOTALMCAP, GIDXNIFTY100
  props.pageProps.selectedSection   TOP_GAINERS | TOP_LOSERS | YEARLY_HIGH | YEARLY_LOW
Filter by index via URL: ?index=GIDXNIFTY100&section=1 (both params needed).
"""

from __future__ import annotations

from typing import Any

from catalyst.schemas import RawItem
from catalyst.sources.moneycontrol import next_data

_LABEL = {
    "TOP_GAINERS": "top gainers",
    "TOP_LOSERS": "top losers",
    "YEARLY_HIGH": "52-week high",
    "YEARLY_LOW": "52-week low",
}


def _pct(ltp: Any, close: Any) -> float | None:
    try:
        return round((float(ltp) / float(close) - 1) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def parse_groww_market(html: str, source_id: str, tag: str | None = "unusual_move") -> list[RawItem]:
    pp = next_data(html)
    section = str(pp.get("selectedSection") or "")
    label = _LABEL.get(section, section.replace("_", " ").lower() or "market movers")
    out = []
    for s in pp.get("stocks") or []:
        name = s.get("companyShortName") or s.get("companyName") or ""
        symbol = s.get("nseScriptCode") or s.get("bseScriptCode") or ""
        pct = _pct(s.get("ltp"), s.get("close"))
        move = f"{pct:+.2f}%" if pct is not None else ""
        extra = f" · {s['tag']}" if s.get("tag") else ""
        out.append(
            RawItem(
                source_id=source_id,
                url=f"https://groww.in/stocks/{s.get('searchId', '')}",
                title=f"{name} ({symbol}) in {label}: {move} at {s.get('ltp')}{extra}".replace("  ", " "),
                summary=f"Prev close {s.get('close')}, 52-week range {s.get('yearLow')}–{s.get('yearHigh')}, "
                f"market cap {s.get('marketCap')} cr",
                outlet="Groww",
                tag=tag,
                company_hint=symbol or None,
                payload={"row": s, "section": section, "index": pp.get("index"), "change_pct": pct},
            )
        )
    return out
