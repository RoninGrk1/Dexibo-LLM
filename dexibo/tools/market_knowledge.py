"""Curated educational fintech concepts for Dexibo to cite (no live prices)."""

from __future__ import annotations

from typing import Any

CONCEPTS: list[dict[str, Any]] = [
    {
        "id": "isa",
        "title": "ISA (Individual Savings Account)",
        "aliases": ["isa", "stocks and shares isa", "cash isa"],
        "summary": (
            "A UK tax-advantaged wrapper for cash or investments. Contributions "
            "count toward an annual allowance set by HMRC. Returns inside an ISA "
            "are generally free of UK income tax and capital gains tax on the "
            "investments held. Product types include Cash ISA and Stocks & Shares ISA. "
            "Rules and allowances change; check GOV.UK for the current tax year."
        ),
    },
    {
        "id": "apr",
        "title": "APR (Annual Percentage Rate)",
        "aliases": ["apr", "annual percentage rate"],
        "summary": (
            "A standardised way to express the yearly cost of borrowing, including "
            "interest and certain mandatory fees. APR helps compare credit products "
            "but may not capture every optional charge or how your usage pattern affects "
            "what you actually pay. For savings, an AER (Annual Equivalent Rate) is "
            "often used instead."
        ),
    },
    {
        "id": "cagr",
        "title": "CAGR (Compound Annual Growth Rate)",
        "aliases": ["cagr", "compound annual growth rate"],
        "summary": (
            "The constant annual rate that would take a starting value to an ending "
            "value over a number of years, assuming compounding. Useful for comparing "
            "growth across periods of different lengths. Past CAGR is not a forecast."
        ),
    },
    {
        "id": "etf",
        "title": "ETF (Exchange-Traded Fund)",
        "aliases": ["etf", "exchange traded fund", "exchange-traded fund"],
        "summary": (
            "An investment fund that typically tracks an index, sector, or strategy "
            "and trades on an exchange like a share. Investors gain diversified exposure "
            "in a single instrument, subject to fees (TER/OCF), tracking difference, "
            "and market price vs NAV. Not all ETFs are low-risk."
        ),
    },
    {
        "id": "volatility",
        "title": "Volatility",
        "aliases": ["volatility", "vol", "standard deviation"],
        "summary": (
            "A statistical measure of how much returns vary around their average. "
            "Higher volatility means larger swings — both up and down. It is a common "
            "input to risk models but does not capture every risk (e.g. liquidity, "
            "tail events, or credit default)."
        ),
    },
    {
        "id": "kyc",
        "title": "KYC (Know Your Customer)",
        "aliases": ["kyc", "know your customer", "customer due diligence"],
        "summary": (
            "Regulatory processes firms use to verify customer identity and assess "
            "risk of money laundering or terrorist financing. Related terms include "
            "CDD (Customer Due Diligence) and AML (Anti-Money Laundering). Banks and "
            "fintechs must apply KYC before opening many account types."
        ),
    },
    {
        "id": "aml",
        "title": "AML (Anti-Money Laundering)",
        "aliases": ["aml", "anti-money laundering", "money laundering"],
        "summary": (
            "Laws and controls that aim to prevent criminals from disguising illicit "
            "funds as legitimate. Obligations typically include customer due diligence, "
            "transaction monitoring, and suspicious activity reporting. Circumventing "
            "AML controls is illegal."
        ),
    },
    {
        "id": "fx",
        "title": "FX (Foreign Exchange)",
        "aliases": ["fx", "forex", "foreign exchange", "currency exchange"],
        "summary": (
            "The market for exchanging one currency for another. Retail customers "
            "usually pay a spread (difference between buy and sell rates) and sometimes "
            "fees. Mid-market rates shown online are not always the rate you receive. "
            "Dexibo does not provide live FX quotes."
        ),
    },
    {
        "id": "open-banking",
        "title": "Open Banking",
        "aliases": ["open banking", "psd2", "account information service"],
        "summary": (
            "In the UK/EU, regulated frameworks (including PSD2 / Open Banking) let "
            "customers grant trusted third parties secure access to account data or "
            "payment initiation via APIs — instead of sharing passwords. Providers "
            "must be authorised; consent can be revoked."
        ),
    },
    {
        "id": "diversification",
        "title": "Diversification",
        "aliases": ["diversification", "diversify", "asset allocation"],
        "summary": (
            "Spreading investments across assets, sectors, or geographies so that "
            "a single adverse event has less impact on the whole portfolio. It reduces "
            "idiosyncratic risk but does not eliminate market risk. Asset allocation "
            "should match goals, horizon, and risk tolerance — seek regulated advice "
            "for personal situations."
        ),
    },
    {
        "id": "inflation",
        "title": "Inflation",
        "aliases": ["inflation", "cpi", "rpi", "purchasing power"],
        "summary": (
            "A sustained rise in the general price level, which erodes purchasing "
            "power of cash. Central banks often target a low positive inflation rate. "
            "Real returns adjust nominal returns for inflation. Official UK measures "
            "include CPI and related indices published by the ONS."
        ),
    },
    {
        "id": "bond",
        "title": "Bond",
        "aliases": ["bond", "gilt", "fixed income", "government bond"],
        "summary": (
            "A debt instrument: the issuer borrows money and typically pays interest "
            "(coupon) and repays principal at maturity. UK government bonds are called "
            "gilts. Bond prices move inversely with yields; credit and interest-rate "
            "risk matter. Educational concept only — not a recommendation."
        ),
    },
    {
        "id": "pension",
        "title": "Pension (UK basics)",
        "aliases": ["pension", "workplace pension", "sipp", "sipps", "auto enrolment"],
        "summary": (
            "Long-term retirement savings, often with tax relief. UK workplace pensions "
            "commonly use auto-enrolment with employer and employee contributions. "
            "SIPPs are self-invested personal pensions. Access rules, tax, and state "
            "pension entitlements are complex — check GOV.UK and Pension Wise."
        ),
    },
    {
        "id": "stablecoin",
        "title": "Stablecoin (basics)",
        "aliases": ["stablecoin", "usdt", "usdc"],
        "summary": (
            "A crypto-asset designed to maintain a stable value relative to a reference "
            "(often a fiat currency), via reserves, algorithms, or other mechanisms. "
            "Risks include reserve quality, redemption, regulation, and smart-contract "
            "failures. Educational overview only — not an endorsement."
        ),
    },
    {
        "id": "sharpe",
        "title": "Sharpe ratio (concept)",
        "aliases": ["sharpe", "sharpe ratio"],
        "summary": (
            "A risk-adjusted performance measure: excess return over a risk-free rate, "
            "divided by volatility (standard deviation of returns). Higher is often "
            "read as better compensation per unit of volatility, but assumptions and "
            "period choice matter. Dexibo's calculator offers only a simplified proxy."
        ),
    },
]


def _aliases(concept: dict[str, Any]) -> list[str]:
    return [a.lower() for a in concept.get("aliases", [])]


def lookup_concept(query: str) -> dict[str, Any] | None:
    """Exact id/title/alias match, or alias contained as a whole phrase in the query."""
    q = query.strip().lower()
    if not q:
        return None

    # Exact matches first
    for concept in CONCEPTS:
        if concept["id"] == q or concept["title"].lower() == q:
            return concept
        if q in _aliases(concept):
            return concept

    # Phrase-in-query (prefer longer aliases to avoid tiny false positives)
    best: tuple[int, dict[str, Any]] | None = None
    for concept in CONCEPTS:
        for alias in _aliases(concept):
            if len(alias) < 3:
                continue
            if alias in q or concept["id"] in q:
                score = len(alias)
                if best is None or score > best[0]:
                    best = (score, concept)
    return best[1] if best else None


def search_concepts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Keyword search over titles and aliases (not full summaries — fewer false hits)."""
    tokens = [t for t in query.lower().split() if len(t) > 2]
    if not tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for concept in CONCEPTS:
        title_blob = " ".join(
            [concept["id"], concept["title"], *_aliases(concept)]
        ).lower()
        score = sum(1 for t in tokens if t in title_blob)
        # Bonus if a full alias appears in the query
        for alias in _aliases(concept):
            if len(alias) >= 3 and alias in query.lower():
                score += 3
        if score:
            scored.append((score, concept))

    scored.sort(key=lambda x: (-x[0], x[1]["title"]))
    return [c for _, c in scored[:limit]]
