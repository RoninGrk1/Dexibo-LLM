"""Conversation loop and history management."""

from __future__ import annotations

from dataclasses import dataclass, field

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
class ChatSession:
    """In-memory multi-turn conversation with a Dexibo model backend."""

    model: BaseModel
    history: list[dict[str, str]] = field(default_factory=list)
    max_history: int = 40
    config: DexiboConfig | None = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = getattr(self.model, "config", None) or load_config()

    def clear(self) -> None:
        self.history.clear()

    def ask(self, user_message: str) -> str:
        """Append a user message, generate a reply, and store both."""
        text = user_message.strip()
        if not text:
            return ""

        cfg = self.config or load_config()

        # --- Guardrails pre-check ---
        if cfg.enable_guardrails:
            pre = check_user_message(text)
            if not pre.get("allowed", True):
                reply = pre.get("reply") or (
                    f"I can't help with that.\n\n_{DISCLAIMER_SHORT}_"
                )
                self.history.append({"role": "user", "content": text})
                self.history.append({"role": "assistant", "content": reply})
                return reply

        self.history.append({"role": "user", "content": text})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

        # Build generation messages with optional RAG + tool instructions + quotes
        gen_messages = list(self.history)
        supplements: list[str] = []

        if cfg.enable_rag:
            chunks = retrieve(text, k=cfg.rag_top_k)
            ctx = format_retrieved_context(chunks)
            if ctx:
                supplements.append(ctx)

        quote_block = ""
        if cfg.enable_quotes:
            sym = detect_quote_symbol(text)
            if sym:
                q = get_quote(sym)
                quote_block = format_quote(q)
                supplements.append(f"[Quote tool result]\n{quote_block}\n[/Quote tool result]")

        calc_payload = None
        if needs_calculator(text):
            # Mock path: run registry directly for clean deterministic answers
            if getattr(self.model, "backend_name", "") == "mock":
                calc_payload = detect_and_run_from_text(text)
            else:
                supplements.append(tool_instructions_block())

        if supplements:
            # Inject as a user supplement so both mock and LLM see it
            gen_messages = [
                *gen_messages[:-1],
                {
                    "role": "user",
                    "content": text
                    + "\n\n"
                    + "\n\n".join(supplements),
                },
            ]

        # Prefer deterministic calc for mock when we already have a payload
        if calc_payload is not None and getattr(self.model, "backend_name", "") == "mock":
            reply = format_tool_result(calc_payload)
            reply = f"{reply}\n\n_{DISCLAIMER_SHORT}_"
            if quote_block:
                reply = f"{quote_block}\n\n{reply}"
        else:
            reply = self.model.generate(gen_messages)

            # LlamaCpp tool-call loop: parse fenced JSON, execute, re-ask once
            if getattr(self.model, "backend_name", "").startswith("llama"):
                parsed = parse_tool_call(reply)
                if parsed:
                    try:
                        payload = execute_tool(parsed["name"], parsed["arguments"])
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

            # If mock didn't hit calc but quotes were asked, surface quote cleanly
            if (
                quote_block
                and getattr(self.model, "backend_name", "") == "mock"
                and "[Quote tool result]" not in reply
                and detect_quote_symbol(text)
            ):
                # Prefer showing the quote when that's the main ask
                if not needs_calculator(text):
                    reply = f"{quote_block}\n\n_{DISCLAIMER_SHORT}_"

        # --- Guardrails post-check ---
        if cfg.enable_guardrails:
            reply = check_assistant_output(reply, user_message=text)

        self.history.append({"role": "assistant", "content": reply})
        return reply

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.history if m["role"] == "user")
