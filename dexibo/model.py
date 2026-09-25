"""Model loading via llama-cpp-python with graceful mock fallback."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from dexibo.config import DexiboConfig, load_config
from dexibo.system_prompt import DISCLAIMER_SHORT, build_system_prompt
from dexibo.tools.market_knowledge import lookup_concept, search_concepts
from dexibo.tools.registry import detect_and_run_from_text, format_tool_result


class BaseModel(ABC):
    """Common interface for real and mock backends."""

    def __init__(self, config: DexiboConfig) -> None:
        self.config = config
        self.system_prompt = build_system_prompt(config)

    @property
    @abstractmethod
    def backend_name(self) -> str:
        ...

    @abstractmethod
    def generate(self, messages: list[dict[str, str]]) -> str:
        """Generate an assistant reply from chat messages (role/content dicts)."""
        ...


class MockModel(BaseModel):
    """Demo backend: calculator + educational knowledge without GGUF weights."""

    @property
    def backend_name(self) -> str:
        return "mock"

    def generate(self, messages: list[dict[str, str]]) -> str:
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        text = user_text.strip()
        # Strip injected supplements for intent detection on the original ask
        primary = text.split("[Retrieved context]")[0].split("[Quote tool result]")[0].strip()
        lower = primary.lower()

        # Greetings
        if re.search(r"\b(hi|hello|hey|greetings)\b", lower) or lower in {
            "hi",
            "hello",
            "hey",
        }:
            return (
                f"Hello — I'm **{self.config.name}**, {self.config.tagline}.\n\n"
                "I'm running in **demo/mock mode** (no GGUF loaded yet). "
                "I can still help with calculators, RAG concepts, and delayed quotes.\n\n"
                "Try `/help`, `/rag open banking`, `/quote AAPL`, or ask about ISAs.\n\n"
                f"_{DISCLAIMER_SHORT}_"
            )

        # Prefer registry-backed calculator (never invent numbers)
        calc_reply = self._try_calc(lower, primary)
        if calc_reply:
            return calc_reply

        # If RAG context was injected, summarise the top chunk educationally
        if "[Retrieved context]" in text:
            # Pull first ### block title/body lightly
            m = re.search(
                r"###\s*\(1\)\s*(.+?)\s*\[.+?\]\s*\(score=[\d.]+\)\n(.*?)(?=\n###|\n\[/Retrieved|\Z)",
                text,
                re.S,
            )
            if m:
                title = m.group(1).strip()
                body = m.group(2).strip()
                # Truncate long bodies
                if len(body) > 900:
                    body = body[:900].rstrip() + "…"
                return (
                    f"**{title}**\n\n{body}\n\n"
                    "_Answer grounded in retrieved educational context (mock mode)._\n\n"
                    f"_{DISCLAIMER_SHORT}_"
                )

        # Surface quote tool result if present
        if "[Quote tool result]" in text:
            qm = re.search(
                r"\[Quote tool result\]\n(.*?)\n\[/Quote tool result\]",
                text,
                re.S,
            )
            if qm:
                return f"{qm.group(1).strip()}\n\n_{DISCLAIMER_SHORT}_"

        # Knowledge lookup
        concept = lookup_concept(primary) or lookup_concept(lower)
        if concept is None:
            hits = search_concepts(primary)
            if hits:
                concept = hits[0]
        if concept:
            aliases = ", ".join(concept.get("aliases", [])) or "—"
            return (
                f"**{concept['title']}**\n\n"
                f"{concept['summary']}\n\n"
                f"*Also known as:* {aliases}\n\n"
                f"_{DISCLAIMER_SHORT}_"
            )

        # Helpful default
        return (
            f"I'm **{self.config.name}** in mock mode — no local GGUF is loaded, "
            "so I answer with calculators, RAG notes, and curated concepts.\n\n"
            "Suggestions:\n"
            "- `/calc compound <principal> <rate%> <years> [n]`\n"
            "- `/rag <query>` — TF-IDF retrieval over knowledge/\n"
            "- `/quote AAPL` — delayed unofficial quote\n"
            "- `/upgrades` — list v0.2 upgrades\n"
            "- Ask about a concept: ISA, APR, CAGR, KYC, ETF, Open Banking…\n"
            "- Download a model: `python scripts/download_model.py`\n\n"
            f"_{DISCLAIMER_SHORT}_"
        )

    def _try_calc(self, lower: str, text: str) -> str | None:
        """Reuse/extend registry so natural language hits real calculator functions."""
        payload = detect_and_run_from_text(text) or detect_and_run_from_text(lower)
        if not payload:
            return None
        return format_tool_result(payload) + f"\n\n_{DISCLAIMER_SHORT}_"


class LlamaCppModel(BaseModel):
    """GGUF inference via llama-cpp-python."""

    def __init__(self, config: DexiboConfig) -> None:
        super().__init__(config)
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                'Install with: pip install "llama-cpp-python>=0.2.90" '
                "or pip install -e \".[llm]\""
            ) from exc

        kwargs: dict[str, Any] = {
            "model_path": str(config.model_path),
            "n_ctx": config.n_ctx,
            "n_gpu_layers": config.n_gpu_layers,
            "verbose": False,
        }
        if config.n_threads is not None:
            kwargs["n_threads"] = config.n_threads

        self._llm = Llama(**kwargs)

    @property
    def backend_name(self) -> str:
        return f"llama.cpp ({self.config.model_path.name})"

    def generate(self, messages: list[dict[str, str]]) -> str:
        chat_messages = [{"role": "system", "content": self.system_prompt}, *messages]
        response = self._llm.create_chat_completion(
            messages=chat_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            repeat_penalty=self.config.repeat_penalty,
        )
        choice = response["choices"][0]
        content = choice["message"]["content"]
        return (content or "").strip()


def load_model(config: DexiboConfig | None = None) -> BaseModel:
    """Load GGUF model or fall back to mock mode."""
    cfg = config or load_config()
    if cfg.use_mock:
        return MockModel(cfg)
    try:
        return LlamaCppModel(cfg)
    except Exception as exc:  # noqa: BLE001 — fall back gracefully
        mock = MockModel(cfg)
        mock._load_error = str(exc)  # type: ignore[attr-defined]
        return mock
