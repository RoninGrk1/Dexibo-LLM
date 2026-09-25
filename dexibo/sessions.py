"""Persistent chat sessions under data/sessions/."""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dexibo.compliance import compliance_export_note
from dexibo.config import PROJECT_ROOT

SESSIONS_DIR = PROJECT_ROOT / "data" / "sessions"


def ensure_sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    return str(uuid.uuid4())


def session_path(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "", session_id)
    if not safe:
        raise ValueError("invalid session id")
    return SESSIONS_DIR / f"{safe}.json"


def create_session(*, backend: str = "mock", session_id: str | None = None) -> dict[str, Any]:
    ensure_sessions_dir()
    sid = session_id or new_session_id()
    now = _now_iso()
    doc: dict[str, Any] = {
        "id": sid,
        "created": now,
        "updated": now,
        "backend": backend,
        "messages": [],
    }
    save_session(doc)
    return doc


def load_session(session_id: str) -> dict[str, Any] | None:
    ensure_sessions_dir()
    path = session_path(session_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_session(doc: dict[str, Any]) -> Path:
    ensure_sessions_dir()
    sid = doc.get("id") or new_session_id()
    doc["id"] = sid
    doc["updated"] = _now_iso()
    if "created" not in doc:
        doc["created"] = doc["updated"]
    path = session_path(sid)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_turn(
    session_id: str,
    *,
    user: str,
    assistant: str,
    backend: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a user/assistant turn and persist."""
    doc = load_session(session_id)
    if doc is None:
        doc = create_session(backend=backend or "unknown", session_id=session_id)
    if backend:
        doc["backend"] = backend
    messages = doc.setdefault("messages", [])
    messages.append({"role": "user", "content": user, "ts": _now_iso()})
    asst: dict[str, Any] = {"role": "assistant", "content": assistant, "ts": _now_iso()}
    if meta:
        asst["meta"] = meta
    messages.append(asst)
    save_session(doc)
    return doc


def list_sessions(*, limit: int = 50) -> list[dict[str, Any]]:
    ensure_sessions_dir()
    items: list[dict[str, Any]] = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items.append(
            {
                "id": doc.get("id", path.stem),
                "created": doc.get("created"),
                "updated": doc.get("updated"),
                "backend": doc.get("backend"),
                "message_count": len(doc.get("messages") or []),
            }
        )
    items.sort(key=lambda x: x.get("updated") or "", reverse=True)
    return items[:limit]


def latest_session() -> dict[str, Any] | None:
    items = list_sessions(limit=1)
    if not items:
        return None
    return load_session(items[0]["id"])


def export_markdown(session_id: str) -> str:
    doc = load_session(session_id)
    if doc is None:
        raise FileNotFoundError(f"session not found: {session_id}")
    lines = [
        f"# Dexibo session `{doc.get('id')}`",
        "",
        f"- Created: {doc.get('created')}",
        f"- Updated: {doc.get('updated')}",
        f"- Backend: {doc.get('backend')}",
        "",
        "---",
        "",
    ]
    for msg in doc.get("messages") or []:
        role = (msg.get("role") or "unknown").upper()
        content = msg.get("content") or ""
        lines.append(f"### {role}")
        lines.append("")
        lines.append(content)
        lines.append("")
    lines.append(compliance_export_note())
    return "\n".join(lines)


def export_csv(session_id: str) -> str:
    """CSV of calc/quote rows when present; otherwise message previews."""
    doc = load_session(session_id)
    if doc is None:
        raise FileNotFoundError(f"session not found: {session_id}")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["ts", "role", "type", "symbol_or_tool", "field", "value", "preview"]
    )

    for msg in doc.get("messages") or []:
        meta = msg.get("meta") or {}
        ts = msg.get("ts") or ""
        role = msg.get("role") or ""
        rtype = meta.get("type") or ""
        data = meta.get("data") or {}
        if rtype == "calc" and isinstance(data, dict):
            tool = data.get("tool") or "calc"
            result = data.get("result") or data
            if isinstance(result, dict):
                for k, v in result.items():
                    if str(k).startswith("_"):
                        continue
                    writer.writerow([ts, role, "calc", tool, k, v, ""])
            else:
                writer.writerow([ts, role, "calc", tool, "result", result, ""])
        elif rtype == "quote" and isinstance(data, dict):
            sym = data.get("symbol") or ""
            for k, v in data.items():
                writer.writerow([ts, role, "quote", sym, k, v, ""])
        else:
            preview = (msg.get("content") or "").replace("\n", " ")[:120]
            writer.writerow([ts, role, rtype or "text", "", "", "", preview])

    note = compliance_export_note().replace("\n", " ")[:200]
    writer.writerow(["", "system", "compliance", "", "note", "", note])
    return buf.getvalue()


__all__ = [
    "SESSIONS_DIR",
    "ensure_sessions_dir",
    "new_session_id",
    "create_session",
    "load_session",
    "save_session",
    "append_turn",
    "list_sessions",
    "latest_session",
    "export_markdown",
    "export_csv",
]
