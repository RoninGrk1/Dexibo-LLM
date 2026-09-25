"""Configuration and branding for Dexibo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root: /workspace/dexibo
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_optional_int(key: str) -> int | None:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return None
    return int(raw)


@dataclass(frozen=True)
class DexiboConfig:
    """Runtime settings for the Dexibo assistant."""

    name: str = "Dexibo"
    tagline: str = "lite fintech intelligence"
    model_path: Path = PROJECT_ROOT / "models" / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    n_ctx: int = 4096
    n_gpu_layers: int = 0
    n_threads: int | None = None
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    force_mock: bool = False
    default_currency: str = "GBP"
    # v0.2 upgrades
    enable_rag: bool = True
    enable_guardrails: bool = True
    enable_quotes: bool = True
    rag_top_k: int = 3

    @property
    def model_exists(self) -> bool:
        return self.model_path.is_file()

    @property
    def use_mock(self) -> bool:
        return self.force_mock or not self.model_exists


def load_config() -> DexiboConfig:
    """Load config from environment variables and .env."""
    model_raw = os.getenv(
        "DEXIBO_MODEL_PATH",
        str(PROJECT_ROOT / "models" / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"),
    )
    model_path = Path(model_raw)
    if not model_path.is_absolute():
        model_path = (PROJECT_ROOT / model_path).resolve()

    return DexiboConfig(
        name=os.getenv("DEXIBO_NAME", "Dexibo"),
        tagline=os.getenv("DEXIBO_TAGLINE", "lite fintech intelligence"),
        model_path=model_path,
        n_ctx=_env_int("DEXIBO_N_CTX", 4096),
        n_gpu_layers=_env_int("DEXIBO_N_GPU_LAYERS", 0),
        n_threads=_env_optional_int("DEXIBO_N_THREADS"),
        max_tokens=_env_int("DEXIBO_MAX_TOKENS", 512),
        temperature=_env_float("DEXIBO_TEMPERATURE", 0.7),
        top_p=_env_float("DEXIBO_TOP_P", 0.9),
        repeat_penalty=_env_float("DEXIBO_REPEAT_PENALTY", 1.1),
        force_mock=_env_bool("DEXIBO_FORCE_MOCK", False),
        default_currency=os.getenv("DEXIBO_DEFAULT_CURRENCY", "GBP").upper(),
        enable_rag=_env_bool("DEXIBO_RAG", True),
        enable_guardrails=_env_bool("DEXIBO_GUARDRAILS", True),
        enable_quotes=_env_bool("DEXIBO_QUOTES", True),
        rag_top_k=_env_int("DEXIBO_RAG_TOP_K", 3),
    )


# Recommended GGUF models that fit ~4GB systems (weights only; runtime adds overhead).
RECOMMENDED_MODELS: list[dict[str, str]] = [
    {
        "id": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "local_name": "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "approx_size": "~2.0 GB",
        "notes": "Default recommendation — strong instruct quality for 3B class.",
    },
    {
        "id": "bartowski/Phi-3.1-mini-4k-instruct-GGUF",
        "filename": "Phi-3.1-mini-4k-instruct-Q4_K_M.gguf",
        "local_name": "Phi-3.1-mini-4k-instruct-Q4_K_M.gguf",
        "approx_size": "~2.4 GB",
        "notes": "Microsoft Phi-3.1 mini; good reasoning in a small footprint.",
    },
    {
        "id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "local_name": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "approx_size": "~4.7 GB",
        "notes": "Heavier option — may exceed 4GB RAM once loaded; prefer Q5_K_S or Q4 on larger machines.",
    },
]
