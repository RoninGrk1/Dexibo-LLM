"""Conversation loop, structured replies, and history management."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from dexibo.config import DexiboConfig, load_config
from dexibo.guardrails import check_assistant_output, check_user_message
from dexibo.model import BaseModel
from dexibo.rag import format_retrieved_context, retrieve
from dexibo.system_prompt import DISCLAIMER_SHORT
from dexibo.tools.quotes import detect_quote_symbol, format_quote, get_quote
from dexibo.tools.registry import (
    detect_and_run_from_text,
    execute_tool,
    format_tool_result,
    needs_calculator,
    parse_tool_call,
    tool_instructions_block,
)


@dataclass
class ChatResult:
    """Structured chat result (markdown-friendly + JSON-mode schema)."""

    text: str
    type: str = "text"  # calc | quote | concept | text | refusal
    data: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = DISCLAIMER_SHORT
    citations: list[dict[str, Any]] = field(default_factory=list)
    refused: bool = False
    refusal_category: str | None = None

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "disclaimer": self.disclaimer,
            "citations": self.citations,
            "text": self.text,
            "refused": self.refused,
            "refusal_category": self.refusal_category,
        }

    def render(self, *, json_mode: bool = False) -> str:
        if json_mode:
            return json.dumps(self.to_schema(), ensure_ascii=False, indent=2)
        return self.text


def citations_from_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map RAG chunks to UI citation chips: {title, doc_id, score}."""
    out: list[dict[str, Any]] = []
    for c in chunks or []:
        out.append(
            {
                "title": c.get("title") or c.get("doc_id") or "source",
                "doc_id": c.get("doc_id") or "",
                "score": c.get("score"),
            }
        )
    return out


def _infer_type(
    *,
    refused: bool,
    calc_payload: dict[str, Any] | None,
    quote_symbol: str | None,
    citations: list[dict[str, Any]],
) -> str:
    if refused:
        return "refusal"
    if calc_payload is not None:
        return "calc"
    if quote_symbol:
        return "quote"
    if citations:
        return "concept"
    return "text"


@dataclass
class ChatSession:
    """In-memory multi-turn conversation with a Dexibo model backend."""

    model: BaseModel
    history: list[dict[str, str]] = field(default_factory=list)
    max_history: int = 40
    config: DexiboConfig | None = None
    session_id: str | None = None
    json_mode: bool | None = None  # None → use config.json_mode
    last_result: ChatResult | None = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = getattr(self.model, "config", None) or load_config()

    def clear(self) -> None:
        self.history.clear()
        self.last_result = None

    def _json_mode(self, override: bool | None = None) -> bool:
        if override is not None:
            return bool(override)
        if self.json_mode is not None:
            return bool(self.json_mode)
        cfg = self.config or load_config()
        return bool(cfg.json_mode)

    def ask(self, user_message: str, *, json_mode: bool | None = None) -> str:
        """Append a user message, generate a reply, and store both.

        Returns markdown by default, or a JSON schema string when JSON mode is on.
        """
        result = self.ask_result(user_message)
        return result.render(json_mode=self._json_mode(json_mode))

    def ask_result(self, user_message: str) -> ChatResult:
        """Full structured ask — always returns ChatResult."""
        text = user_message.strip()
        if not text:
            empty = ChatResult(text="", type="text")
            self.last_result = empty
            return empty

        cfg = self.config or load_config()
        citations: list[dict[str, Any]] = []
        calc_payload: dict[str, Any] | None = None
        quote_symbol: str | None = None
        quote_data: dict[str, Any] | None = None

        # --- Guardrails pre-check ---
        if cfg.enable_guardrails:
            pre = check_user_message(text, session_id=self.session_id)
            if not pre.get("allowed", True):
                reply = pre.get("reply") or (
                    f"I can't help with that.\n\n_{DISCLAIMER_SHORT}_"
                )
                self.history.append({"role": "user", "content": text})
                self.history.append({"role": "assistant", "content": reply})
                result = ChatResult(
                    text=reply,
                    type="refusal",
                    data={"category": pre.get("category")},
                    disclaimer=DISCLAIMER_SHORT,
                    refused=True,
                    refusal_category=pre.get("category"),
                )
                self.last_result = result
                return result

        self.history.append({"role": "user", "content": text})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

        gen_messages = list(self.history)
        supplements: list[str] = []
        chunks: list[dict[str, Any]] = []

        if cfg.enable_rag:
            chunks = retrieve(text, k=cfg.rag_top_k)
            citations = citations_from_chunks(chunks)
            ctx = format_retrieved_context(chunks)
            if ctx:
                supplements.append(ctx)

        quote_block = ""
        if cfg.enable_quotes:
            quote_symbol = detect_quote_symbol(text)
            if quote_symbol:
                q = get_quote(quote_symbol)
                quote_data = q if isinstance(q, dict) else {"raw": q}
                quote_block = format_quote(q)
                supplements.append(
                    f"[Quote tool result]\n{quote_block}\n[/Quote tool result]"
                )

        if needs_calculator(text):
            if getattr(self.model, "backend_name", "") == "mock":
                calc_payload = detect_and_run_from_text(text)
            else:
                supplements.append(tool_instructions_block())

        if supplements:
            gen_messages = [
                *gen_messages[:-1],
                {
                    "role": "user",
                    "content": text + "\n\n" + "\n\n".join(supplements),
                },
            ]

        if calc_payload is not None and getattr(self.model, "backend_name", "") == "mock":
            reply = format_tool_result(calc_payload)
            reply = f"{reply}\n\n_{DISCLAIMER_SHORT}_"
            if quote_block:
                reply = f"{quote_block}\n\n{reply}"
        else:
            reply = self.model.generate(gen_messages)

            if getattr(self.model, "backend_name", "").startswith("llama"):
                parsed = parse_tool_call(reply)
                if parsed:
                    try:
                        payload = execute_tool(parsed["name"], parsed["arguments"])
                        calc_payload = payload
                        tool_text = format_tool_result(payload)
                    except (TypeError, ValueError) as exc:
                        tool_text = f"Tool error: {exc}"
                    follow = list(gen_messages) + [
                        {"role": "assistant", "content": reply},
                        {
                            "role": "user",
                            "content": (
                                f"[Tool result]\n{tool_text}\n[/Tool result]\n"
                                "Using only the tool result above, give a clear "
                                "educational natural-language answer. Do not invent numbers."
                            ),
                        },
                    ]
                    reply = self.model.generate(follow)

            if (
                quote_block
                and getattr(self.model, "backend_name", "") == "mock"
                and "[Quote tool result]" not in reply
                and detect_quote_symbol(text)
            ):
                if not needs_calculator(text):
                    reply = f"{quote_block}\n\n_{DISCLAIMER_SHORT}_"

        if cfg.enable_guardrails:
            reply = check_assistant_output(reply, user_message=text)

        self.history.append({"role": "assistant", "content": reply})

        rtype = _infer_type(
            refused=False,
            calc_payload=calc_payload,
            quote_symbol=quote_symbol,
            citations=citations,
        )
        data: dict[str, Any] = {}
        if calc_payload is not None:
            data = {
                "tool": calc_payload.get("tool"),
                "arguments": calc_payload.get("arguments"),
                "result": calc_payload.get("result", calc_payload),
            }
        elif quote_data is not None:
            data = quote_data
        elif citations:
            data = {"topics": [c.get("title") for c in citations]}

        result = ChatResult(
            text=reply,
            type=rtype,
            data=data,
            disclaimer=DISCLAIMER_SHORT,
            citations=citations,
        )
        self.last_result = result
        return result

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.history if m["role"] == "user")


__all__ = [
    "ChatSession",
    "ChatResult",
    "citations_from_chunks",
    "asdict",
]
