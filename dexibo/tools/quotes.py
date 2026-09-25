"""Delayed market quotes via public Yahoo Finance endpoints (stdlib urllib only)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

_UA = (
    "Mozilla/5.0 (compatible; Dexibo/0.4; +https://github.com/example/dexibo) "
    "Educational-quote-client"
)
_TIMEOUT = 8

_SYMBOL_RE = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z]{1,4})?)\b")
_PRICE_HINT = re.compile(
    r"\b(price|quote|trading\s+at|how\s+much\s+is|what(?:'s|\s+is)\s+the\s+price)\b",
    re.I,
)


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — public URL
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def get_quote(symbol: str) -> dict[str, Any]:
    """Fetch a delayed unofficial quote for *symbol*.

    Returns a dict with price, currency, as_of, source labelled delayed/unofficial.
    On failure returns {ok: False, error: ..., symbol: ...} — never raises for network.
    """
    sym = (symbol or "").strip().upper()
    if not sym or not re.fullmatch(r"[A-Z0-9.^_-]{1,20}", sym):
        return {
            "ok": False,
            "symbol": sym,
            "error": "invalid symbol",
            "source": "delayed / unofficial (Yahoo Finance public chart)",
        }

    # Yahoo chart endpoint (delayed for many instruments)
    enc = urllib.parse.quote(sym)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}"
        f"?interval=1d&range=1d"
    )
    try:
        data = _fetch_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "symbol": sym,
            "error": f"quote fetch failed: {exc}",
            "source": "delayed / unofficial (Yahoo Finance public chart)",
        }

    try:
        result = data["chart"]["result"][0]
        meta = result.get("meta") or {}
        price = meta.get("regularMarketPrice")
        if price is None:
            # fallback: last close
            closes = (result.get("indicators") or {}).get("quote", [{}])[0].get("close") or []
            closes = [c for c in closes if c is not None]
            price = closes[-1] if closes else None
        currency = meta.get("currency") or "—"
        ts = meta.get("regularMarketTime")
        if isinstance(ts, (int, float)):
            as_of = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        else:
            as_of = datetime.now(tz=timezone.utc).isoformat()
        if price is None:
            raise KeyError("no price in response")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        change = None
        change_pct = None
        if prev is not None:
            try:
                prev_f = float(prev)
                price_f = float(price)
                if prev_f != 0:
                    change = price_f - prev_f
                    change_pct = (change / prev_f) * 100.0
            except (TypeError, ValueError):
                pass
        out: dict[str, Any] = {
            "ok": True,
            "symbol": meta.get("symbol") or sym,
            "price": float(price),
            "currency": currency,
            "as_of": as_of,
            "exchange": meta.get("exchangeName") or meta.get("fullExchangeName"),
            "source": "delayed / unofficial (Yahoo Finance public chart)",
            "note": (
                "Delayed unofficial quote for education only — not a live feed, "
                "not advice, verify with your broker."
            ),
        }
        if prev is not None:
            try:
                out["previous_close"] = float(prev)
            except (TypeError, ValueError):
                pass
        if change is not None:
            out["change"] = round(change, 6)
        if change_pct is not None:
            out["change_pct"] = round(change_pct, 4)
        return out
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return {
            "ok": False,
            "symbol": sym,
            "error": f"unexpected quote payload: {exc}",
            "source": "delayed / unofficial (Yahoo Finance public chart)",
        }


def format_quote(quote: dict[str, Any]) -> str:
    """Pretty markdown for a get_quote() result."""
    if not quote.get("ok"):
        return (
            f"**Quote unavailable** for `{quote.get('symbol', '?')}`.\n"
            f"- Error: {quote.get('error', 'unknown')}\n"
            f"- Source: {quote.get('source', 'delayed / unofficial')}\n"
            "_Hard-failed gracefully (offline or blocked)._"
        )
    lines = [
        f"**{quote['symbol']}** — delayed unofficial quote",
        f"- Price: {quote['price']:,.4g} {quote.get('currency', '')}".rstrip(),
        f"- As of: {quote.get('as_of', '—')} (UTC)",
    ]
    if quote.get("change_pct") is not None:
        sign = "+" if quote["change_pct"] >= 0 else ""
        lines.append(f"- Change: {sign}{quote['change_pct']:.2f}%")
    if quote.get("exchange"):
        lines.append(f"- Exchange: {quote['exchange']}")
    lines.append(f"- Source: {quote['source']}")
    if quote.get("note"):
        lines.append(f"- Note: {quote['note']}")
    return "\n".join(lines)


def detect_quote_symbol(user_message: str) -> str | None:
    """If the user asks for a price/quote, return a likely ticker, else None."""
    text = user_message or ""
    if not _PRICE_HINT.search(text) and not re.search(
        r"\b(?:quote|ticker)\b", text, re.I
    ):
        # also allow bare "what's AAPL" style with known pattern
        if not re.search(r"\b(aapl|msft|googl|vwrl\.l|tsla|amzn)\b", text, re.I):
            return None
    # Prefer explicit "price of X" / "quote X"
    m = re.search(
        r"(?:price\s+of|quote(?:\s+for)?|ticker)\s+([A-Za-z]{1,5}(?:\.[A-Za-z]{1,4})?)",
        text,
        re.I,
    )
    if m:
        return m.group(1).upper()
    # Uppercase tickers in the message
    uppers = _SYMBOL_RE.findall(text.upper())
    # Filter common English words mistaken as tickers
    skip = {
        "I",
        "A",
        "THE",
        "USD",
        "GBP",
        "EUR",
        "ISA",
        "APR",
        "AER",
        "ETF",
        "KYC",
        "AML",
        "CAGR",
        "SEPA",
        "WHAT",
        "PRICE",
        "QUOTE",
        "FOR",
        "OF",
        "IS",
        "HOW",
        "MUCH",
    }
    for sym in uppers:
        if sym not in skip and len(sym) >= 2:
            return sym
    # lowercase known demos
    m2 = re.search(r"\b(aapl|msft|googl|tsla|amzn|vwrl\.l)\b", text, re.I)
    if m2:
        return m2.group(1).upper()
    return None



def parse_watchlist_symbols(raw: str | None, default: str = "AAPL,MSFT,VWRL.L,BTC-USD") -> list[str]:
    """Parse comma-separated watchlist symbols from env or config string."""
    src = (raw if raw is not None and str(raw).strip() else default)
    out: list[str] = []
    seen: set[str] = set()
    for part in str(src).split(","):
        sym = part.strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out or ["AAPL", "MSFT", "VWRL.L", "BTC-USD"]


def get_watchlist(symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch quotes for a list of symbols; each failure is a graceful ok=False entry."""
    syms = symbols if symbols is not None else parse_watchlist_symbols(None)
    return [get_quote(s) for s in syms]


__all__ = ["get_quote", "format_quote", "detect_quote_symbol", "parse_watchlist_symbols", "get_watchlist"]
