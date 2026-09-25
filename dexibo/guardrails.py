"""Compliance / advice guardrails for Dexibo."""

from __future__ import annotations

import os
import re
from typing import Any

from dexibo.system_prompt import DISCLAIMER_SHORT

# Pre-check: refuse / redirect
_REFUSAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b("
            r"launder\s+money|money\s+launder|"
            r"how\s+to\s+(?:hide|conceal)\s+(?:funds|money|proceeds)|"
            r"structure\s+(?:deposits|transactions)\s+to\s+avoid|"
            r"smurf(?:ing)?"
            r")\b",
            re.I,
        ),
        "money_laundering",
    ),
    (
        re.compile(
            r"\b("
            r"evade\s+kyc|bypass\s+kyc|avoid\s+kyc|skip\s+kyc|"
            r"fake\s+(?:id|identity|documents?)\s+for\s+(?:bank|kyc|account)|"
            r"help\s+me\s+evade\s+kyc"
            r")\b",
            re.I,
        ),
        "kyc_evasion",
    ),
    (
        re.compile(
            r"\b("
            r"pump\s+and\s+dump|market\s+manipulat|"
            r"insider\s+trad(?:e|ing)?|"
            r"spoof(?:ing)?\s+(?:the\s+)?(?:order\s+)?book|"
            r"front[\s-]?run(?:ning)?"
            r")\b",
            re.I,
        ),
        "market_manipulation",
    ),
    (
        re.compile(
            r"\b("
            r"how\s+to\s+(?:commit\s+)?fraud|"
            r"phishing\s+(?:kit|template)|"
            r"social\s+engineer(?:ing)?\s+(?:a\s+)?(?:bank|victim)|"
            r"steal\s+(?:card|account)\s+(?:numbers?|details)"
            r")\b",
            re.I,
        ),
        "fraud",
    ),
]

_REFUSAL_REPLY = (
    "**I can't help with that.**\n\n"
    "Dexibo refuses requests involving fraud, money laundering, market manipulation, "
    "or evading KYC/AML controls.\n\n"
    "I *can* explain — at a high level — why these protections exist, what regulated "
    "firms typically check, and how consumers stay safe. Ask an educational question "
    "instead (e.g. \"What is AML?\" or \"Why do banks ask for ID?\").\n\n"
    f"_{DISCLAIMER_SHORT}_"
)

# Post-check: personalised advice patterns
_ADVICE_PATTERNS = [
    re.compile(r"\byou should (?:buy|sell|invest in|put (?:all|your) money)\b", re.I),
    re.compile(r"\bI recommend (?:you )?(?:buy|sell|invest)\b", re.I),
    re.compile(r"\bguaranteed (?:returns?|profit|income)\b", re.I),
    re.compile(r"\bthis (?:stock|share|coin|token) will (?:definitely|certainly)\b", re.I),
    re.compile(r"\bbuy\s+[A-Z]{1,5}\s+now\b"),
    re.compile(r"\ballocate\s+\d+\s*%\s+of\s+your\s+(?:portfolio|savings|money)\b", re.I),
]

_INVESTMENT_HINT = re.compile(
    r"\b("
    r"invest|investment|isa|sipp|etf|stock|share|bond|gilt|portfolio|"
    r"equity|equities|pension|fund|return|cagr|dividend|broker|trading"
    r")\b",
    re.I,
)

_SOFTEN_PREFIX = (
    "**Note:** The previous wording sounded like personalised investment advice. "
    "Here is a softened educational version:\n\n"
)


def guardrails_enabled(config_flag: bool | None = None) -> bool:
    """Resolve whether guardrails are on (env default on)."""
    if config_flag is not None:
        return bool(config_flag)
    raw = os.getenv("DEXIBO_GUARDRAILS", "1")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def check_user_message(
    text: str,
    *,
    session_id: str | None = None,
    audit: bool = True,
) -> dict[str, Any]:
    """Pre-check user input.

    Returns {allowed: bool, category: str|None, reply: str|None}.
    If allowed is False, callers should return `reply` and skip generation.
    When refused, appends a structured JSONL audit entry (unless audit=False).
    """
    msg = text or ""
    for pattern, category in _REFUSAL_PATTERNS:
        if pattern.search(msg):
            if audit:
                try:
                    from dexibo.compliance import log_refusal

                    log_refusal(
                        category=category,
                        user_message=msg,
                        session_id=session_id,
                    )
                except Exception:  # noqa: BLE001 — never break the chat path
                    pass
            return {
                "allowed": False,
                "category": category,
                "reply": _REFUSAL_REPLY,
            }
    return {"allowed": True, "category": None, "reply": None}


def _looks_like_advice(text: str) -> bool:
    return any(p.search(text or "") for p in _ADVICE_PATTERNS)


def _ensure_disclaimer(text: str) -> str:
    body = (text or "").rstrip()
    if DISCLAIMER_SHORT.lower() in body.lower():
        return body
    if not body:
        return f"_{DISCLAIMER_SHORT}_"
    return f"{body}\n\n_{DISCLAIMER_SHORT}_"


def check_assistant_output(text: str, *, user_message: str = "") -> str:
    """Post-check assistant output: soften advice-like wording; force disclaimer."""
    out = text or ""
    if _looks_like_advice(out):
        softened = out
        softened = re.sub(
            r"\byou should (buy|sell|invest in)\b",
            r"some investors may consider (\1) — this is not a recommendation that you do so",
            softened,
            flags=re.I,
        )
        softened = re.sub(
            r"\bI recommend (?:you )?(buy|sell|invest)\b",
            r"Educationally, people sometimes look at (\1) options — not a personal recommendation",
            softened,
            flags=re.I,
        )
        softened = re.sub(
            r"\bguaranteed (returns?|profit|income)\b",
            r"there are no guaranteed \1 in markets",
            softened,
            flags=re.I,
        )
        softened = re.sub(
            r"\bbuy\s+([A-Z]{1,5})\s+now\b",
            r"discussing \1 as an example only",
            softened,
        )
        out = _SOFTEN_PREFIX + softened

    if _INVESTMENT_HINT.search(out) or _INVESTMENT_HINT.search(user_message or ""):
        out = _ensure_disclaimer(out)
    return out


__all__ = [
    "guardrails_enabled",
    "check_user_message",
    "check_assistant_output",
    "DISCLAIMER_SHORT",
]
