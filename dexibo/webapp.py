"""FastAPI web UI for Dexibo — chat, sessions, scenarios, compliance."""

from __future__ import annotations

import json
import re
import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from dexibo import __version__
from dexibo.chat import ChatSession
from dexibo.compliance import compliance_payload
from dexibo.config import PROJECT_ROOT, DexiboConfig, load_config
from dexibo.model import BaseModel as DexiboModel
from dexibo.model import load_model
from dexibo.sessions import (
    append_turn,
    create_session,
    export_csv,
    export_markdown,
    latest_session,
    list_sessions,
    load_session,
    new_session_id,
)
from dexibo.tools.quotes import format_quote, get_quote, get_watchlist
from dexibo.tools.scenarios import SCENARIO_HANDLERS, run_scenario

WEB_DIR = PROJECT_ROOT / "web"

_lock = threading.Lock()
_config: DexiboConfig | None = None
_model: DexiboModel | None = None
_sessions: dict[str, ChatSession] = {}
_rate_hits: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()


def _ensure_runtime() -> tuple[DexiboConfig, DexiboModel]:
    global _config, _model
    with _lock:
        if _config is None:
            _config = load_config()
        if _model is None:
            _model = load_model(_config)
        return _config, _model


def _get_or_create_session(
    session_id: str | None,
    *,
    json_mode: bool | None = None,
) -> tuple[str, ChatSession]:
    cfg, model = _ensure_runtime()
    sid = (session_id or "").strip() or new_session_id()
    with _lock:
        session = _sessions.get(sid)
        if session is None:
            doc = load_session(sid)
            session = ChatSession(model=model, config=cfg, session_id=sid)
            if doc and doc.get("messages"):
                session.history = [
                    {"role": m["role"], "content": m.get("content") or ""}
                    for m in doc["messages"]
                    if m.get("role") in {"user", "assistant"}
                ]
            else:
                create_session(backend=model.backend_name, session_id=sid)
            _sessions[sid] = session
        session.session_id = sid
        if json_mode is not None:
            session.json_mode = json_mode
        return sid, session


def _persist_turn(
    sid: str,
    *,
    user: str,
    assistant: str,
    backend: str,
    result: Any,
) -> None:
    meta: dict[str, Any] = {}
    if result is not None:
        meta = {
            "type": getattr(result, "type", None),
            "data": getattr(result, "data", None),
            "citations": getattr(result, "citations", None),
            "refused": getattr(result, "refused", False),
        }
    try:
        append_turn(sid, user=user, assistant=assistant, backend=backend, meta=meta)
    except Exception:
        pass


def _chunk_text(text: str, *, words_per_chunk: int = 2) -> Iterator[str]:
    if not text:
        return
    parts = re.findall(r"\S+\s*|\s+", text)
    if not parts:
        step = max(1, min(8, len(text)))
        for i in range(0, len(text), step):
            yield text[i : i + step]
        return
    buf: list[str] = []
    for part in parts:
        buf.append(part)
        if len(buf) >= words_per_chunk:
            yield "".join(buf)
            buf = []
    if buf:
        yield "".join(buf)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _check_api_key(request: Request, cfg: DexiboConfig) -> None:
    if not cfg.api_key:
        return
    auth = request.headers.get("authorization") or ""
    xkey = request.headers.get("x-api-key") or ""
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    elif xkey:
        token = xkey.strip()
    if token != cfg.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _check_rate_limit(request: Request, cfg: DexiboConfig) -> None:
    limit = max(1, int(cfg.rate_limit_per_minute or 60))
    ip = _client_ip(request)
    now = time.time()
    window = 60.0
    with _rate_lock:
        q = _rate_hits[ip]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        q.append(now)


class ApiGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health":
            cfg, _ = _ensure_runtime()
            try:
                _check_api_key(request, cfg)
                _check_rate_limit(request, cfg)
            except HTTPException as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                )
        return await call_next(request)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    as_json: bool | None = Field(
        None,
        alias="json",
        description="If true, wrap reply in structured JSON schema",
    )

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    backend: str
    type: str | None = None
    data: dict[str, Any] | None = None
    disclaimer: str | None = None
    citations: list[dict[str, Any]] | None = None
    structured: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    backend: str
    name: str
    tagline: str
    flags: dict[str, Any]


class ScenarioRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_runtime()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Dexibo",
        description="lite fintech intelligence — web chat",
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(ApiGuardMiddleware)

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
                "watchlist": list(cfg.watchlist),
                "json_mode": cfg.json_mode,
                "jurisdiction": cfg.jurisdiction,
                "api_key_required": bool(cfg.api_key),
                "rate_limit_per_minute": cfg.rate_limit_per_minute,
            },
        )

    @application.get("/api/compliance")
    def compliance() -> dict[str, str]:
        return compliance_payload()

    @application.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest) -> ChatResponse:
        text = body.message.strip()
        if not text:
            raise HTTPException(status_code=400, detail="message must not be empty")
        sid, session = _get_or_create_session(body.session_id, json_mode=body.as_json)
        try:
            result = session.ask_result(text)
            use_json = session._json_mode(body.as_json)
            reply = result.render(json_mode=use_json)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"chat failed: {exc}") from exc
        _persist_turn(
            sid,
            user=text,
            assistant=result.text,
            backend=session.model.backend_name,
            result=result,
        )
        structured = result.to_schema() if use_json else None
        return ChatResponse(
            reply=reply,
            session_id=sid,
            backend=session.model.backend_name,
            type=result.type,
            data=result.data or None,
            disclaimer=result.disclaimer,
            citations=result.citations or None,
            structured=structured,
        )

    @application.post("/api/chat/stream")
    def chat_stream(body: ChatRequest) -> StreamingResponse:
        text = body.message.strip()
        if not text:
            raise HTTPException(status_code=400, detail="message must not be empty")

        def event_gen() -> Iterator[str]:
            try:
                sid, session = _get_or_create_session(
                    body.session_id, json_mode=body.as_json
                )
                result = session.ask_result(text)
                use_json = session._json_mode(body.as_json)
                out_text = result.render(json_mode=use_json)
                for piece in _chunk_text(out_text):
                    yield _sse({"type": "token", "text": piece})
                    time.sleep(0.012)
                _persist_turn(
                    sid,
                    user=text,
                    assistant=result.text,
                    backend=session.model.backend_name,
                    result=result,
                )
                done: dict[str, Any] = {
                    "type": "done",
                    "session_id": sid,
                    "backend": session.model.backend_name,
                    "reply_type": result.type,
                    "citations": result.citations,
                    "disclaimer": result.disclaimer,
                }
                if use_json:
                    done["structured"] = result.to_schema()
                yield _sse(done)
            except Exception as exc:
                yield _sse({"type": "error", "message": f"chat failed: {exc}"})

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @application.get("/api/watchlist")
    def watchlist() -> dict[str, Any]:
        cfg, _ = _ensure_runtime()
        if not cfg.enable_quotes:
            return {
                "ok": False,
                "error": "quotes disabled",
                "symbols": list(cfg.watchlist),
                "quotes": [],
                "label": "Delayed · unofficial",
            }
        quotes = get_watchlist(list(cfg.watchlist))
        return {
            "ok": True,
            "symbols": list(cfg.watchlist),
            "quotes": quotes,
            "label": "Delayed · unofficial",
        }

    @application.get("/api/quote/{symbol}")
    def quote(symbol: str) -> dict[str, Any]:
        cfg, _ = _ensure_runtime()
        if not cfg.enable_quotes:
            raise HTTPException(status_code=503, detail="quotes disabled")
        q = get_quote(symbol)
        return {"quote": q, "formatted": format_quote(q)}

    @application.get("/api/sessions")
    def sessions_list() -> dict[str, Any]:
        return {"sessions": list_sessions(limit=50)}

    @application.get("/api/sessions/latest")
    def sessions_latest() -> dict[str, Any]:
        doc = latest_session()
        if doc is None:
            return {"session": None}
        return {"session": doc}

    @application.get("/api/sessions/{session_id}")
    def sessions_get(session_id: str) -> dict[str, Any]:
        doc = load_session(session_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="session not found")
        return {"session": doc}

    @application.get("/api/sessions/{session_id}/export.md")
    def sessions_export_md(session_id: str) -> PlainTextResponse:
        try:
            md = export_markdown(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="session not found") from None
        return PlainTextResponse(
            md,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="dexibo-{session_id}.md"'
            },
        )

    @application.get("/api/sessions/{session_id}/export.csv")
    def sessions_export_csv(session_id: str) -> PlainTextResponse:
        try:
            csv_text = export_csv(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="session not found") from None
        return PlainTextResponse(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="dexibo-{session_id}.csv"'
            },
        )

    @application.post("/api/sessions/new")
    def sessions_new() -> dict[str, Any]:
        cfg, model = _ensure_runtime()
        doc = create_session(backend=model.backend_name)
        with _lock:
            _sessions[doc["id"]] = ChatSession(
                model=model, config=cfg, session_id=doc["id"]
            )
        return {"session": doc}

    @application.post("/api/scenarios/{name}")
    def scenarios_run(name: str, body: ScenarioRequest) -> dict[str, Any]:
        try:
            result = run_scenario(name, body.params)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=f"bad params: {exc}") from exc
        return {"ok": True, "scenario": name, "result": result}

    @application.get("/api/scenarios")
    def scenarios_list() -> dict[str, Any]:
        return {"scenarios": sorted(SCENARIO_HANDLERS.keys())}

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


app = create_app()
