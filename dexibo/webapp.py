"""FastAPI web UI for Dexibo — single-page chat + API."""

from __future__ import annotations

import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dexibo import __version__
from dexibo.chat import ChatSession
from dexibo.config import PROJECT_ROOT, DexiboConfig, load_config
from dexibo.model import BaseModel as DexiboModel
from dexibo.model import load_model
from dexibo.tools.quotes import format_quote, get_quote

WEB_DIR = PROJECT_ROOT / "web"

# Module-level state (populated on lifespan startup)
_lock = threading.Lock()
_config: DexiboConfig | None = None
_model: DexiboModel | None = None
_sessions: dict[str, ChatSession] = {}


def _ensure_runtime() -> tuple[DexiboConfig, DexiboModel]:
    global _config, _model
    with _lock:
        if _config is None:
            _config = load_config()
        if _model is None:
            _model = load_model(_config)
        return _config, _model


def _get_or_create_session(session_id: str | None) -> tuple[str, ChatSession]:
    cfg, model = _ensure_runtime()
    sid = (session_id or "").strip() or str(uuid.uuid4())
    with _lock:
        session = _sessions.get(sid)
        if session is None:
            session = ChatSession(model=model, config=cfg)
            _sessions[sid] = session
        return sid, session


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    session_id: str | None = Field(None, description="Optional session id")


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    backend: str


class HealthResponse(BaseModel):
    status: str
    version: str
    backend: str
    name: str
    tagline: str
    flags: dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eager-load model so first chat is snappy (mock is instant)
    _ensure_runtime()
    yield


def create_app() -> FastAPI:
    """Application factory for Dexibo web UI."""
    application = FastAPI(
        title="Dexibo",
        description="lite fintech intelligence — web chat",
        version=__version__,
        lifespan=lifespan,
    )

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        cfg, model = _ensure_runtime()
        return HealthResponse(
            status="ok",
            version=__version__,
            backend=model.backend_name,
            name=cfg.name,
            tagline=cfg.tagline,
            flags={
                "rag": cfg.enable_rag,
                "guardrails": cfg.enable_guardrails,
                "quotes": cfg.enable_quotes,
                "rag_top_k": cfg.rag_top_k,
                "mock": cfg.use_mock,
            },
        )

    @application.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest) -> ChatResponse:
        text = body.message.strip()
        if not text:
            raise HTTPException(status_code=400, detail="message must not be empty")
        sid, session = _get_or_create_session(body.session_id)
        try:
            reply = session.ask(text)
        except Exception as exc:  # noqa: BLE001 — surface cleanly to client
            raise HTTPException(status_code=500, detail=f"chat failed: {exc}") from exc
        return ChatResponse(
            reply=reply,
            session_id=sid,
            backend=session.model.backend_name,
        )

    @application.get("/api/quote/{symbol}")
    def quote(symbol: str) -> dict[str, Any]:
        cfg, _ = _ensure_runtime()
        if not cfg.enable_quotes:
            raise HTTPException(status_code=503, detail="quotes disabled")
        q = get_quote(symbol)
        return {
            "quote": q,
            "formatted": format_quote(q),
        }

    @application.get("/")
    def index() -> FileResponse:
        index_path = WEB_DIR / "index.html"
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="web/index.html missing")
        return FileResponse(index_path)

    if WEB_DIR.is_dir():
        application.mount(
            "/static",
            StaticFiles(directory=str(WEB_DIR)),
            name="static",
        )
        # Also expose css/js/favicon at root-relative paths used by index.html
        @application.get("/styles.css")
        def styles() -> FileResponse:
            return FileResponse(WEB_DIR / "styles.css", media_type="text/css")

        @application.get("/app.js")
        def app_js() -> FileResponse:
            return FileResponse(
                WEB_DIR / "app.js", media_type="application/javascript"
            )

        @application.get("/favicon.svg")
        def favicon() -> FileResponse:
            return FileResponse(WEB_DIR / "favicon.svg", media_type="image/svg+xml")

    return application


# ASGI entry for uvicorn: `uvicorn dexibo.webapp:app`
app = create_app()
