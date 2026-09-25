"""Trust & compliance helpers — jurisdiction banners, footers, refusal audit."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dexibo.config import PROJECT_ROOT
from dexibo.system_prompt import DISCLAIMER_SHORT

AUDIT_DIR = PROJECT_ROOT / "data" / "audit"
REFUSALS_LOG = AUDIT_DIR / "refusals.jsonl"

_JURISDICTION_BANNERS: dict[str, str] = {
    "UK": (
        "Jurisdiction framing: United Kingdom / Europe. Educational content may "
        "reference FCA, HMRC, and UK consumer protections. Rules differ elsewhere."
    ),
    "EU": (
        "Jurisdiction framing: European Union / EEA. Educational content may "
        "reference EU consumer and markets rules. National rules still apply."
    ),
    "US": (
        "Jurisdiction framing: United States (educational). Rules differ by state "
        "and regulator — verify locally."
    ),
}


def get_jurisdiction() -> str:
    raw = (os.getenv("DEXIBO_JURISDICTION") or "UK").strip().upper()
    return raw or "UK"


def jurisdiction_banner(jurisdiction: str | None = None) -> str:
    """Short banner for UI / API describing jurisdiction framing."""
    j = (jurisdiction or get_jurisdiction()).upper()
    return _JURISDICTION_BANNERS.get(
        j,
        (
            f"Jurisdiction framing: {j}. Educational only — verify rules for your "
            "location with official sources."
        ),
    )


def session_compliance_footer() -> str:
    """Always-visible short disclaimer for sessions / UI footer."""
    return DISCLAIMER_SHORT


def compliance_export_note(jurisdiction: str | None = None) -> str:
    """Note appended when exporting a session."""
    j = jurisdiction or get_jurisdiction()
    return (
        f"---\n"
        f"**Compliance note**\n"
        f"- Jurisdiction framing: {j}\n"
        f"- {DISCLAIMER_SHORT}\n"
        f"- Dexibo is educational software, not a regulated advice service.\n"
    )


def ensure_audit_dir() -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return AUDIT_DIR


def log_refusal(
    *,
    category: str,
    user_message: str,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a structured refusal audit entry as JSONL.

    Returns the entry written (also useful for tests).
    """
    ensure_audit_dir()
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "refusal",
        "category": category,
        "jurisdiction": get_jurisdiction(),
        "session_id": session_id,
        "user_message_preview": (user_message or "")[:500],
    }
    if extra:
        entry["extra"] = extra
    with REFUSALS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def compliance_payload() -> dict[str, str]:
    """Payload for GET /api/compliance."""
    j = get_jurisdiction()
    return {
        "jurisdiction": j,
        "banner": jurisdiction_banner(j),
        "disclaimer": session_compliance_footer(),
        "export_note": compliance_export_note(j),
    }


__all__ = [
    "AUDIT_DIR",
    "REFUSALS_LOG",
    "get_jurisdiction",
    "jurisdiction_banner",
    "session_compliance_footer",
    "compliance_export_note",
    "log_refusal",
    "compliance_payload",
    "ensure_audit_dir",
    "DISCLAIMER_SHORT",
]
