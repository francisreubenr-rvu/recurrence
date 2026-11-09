"""FastAPI app: JSON API + a single-page console at /.

Run:  uvicorn app.server:app --reload --port 8000
Offline (no keys, fake memory, template answers):  RECURRENCE_OFFLINE=1 uvicorn app.server:app
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from recurrence.agent import RecurrenceAgent
from recurrence.config import Settings, build_llm, build_memory
from recurrence.seed import load_data, seed

log = logging.getLogger("recurrence.server")

STATIC = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    ),
}


class StrictModel(BaseModel):
    """Trim whitespace so a value of only spaces fails min_length."""

    model_config = ConfigDict(str_strip_whitespace=True)


class AskIn(StrictModel):
    alert: str = Field(min_length=3, max_length=8000)
    engineer: str = Field(min_length=1, max_length=120)
    service: str = Field(min_length=1, max_length=120)
    memory_on: bool = True
    now: str | None = Field(default=None, max_length=40)  # ISO time; lets the demo replay "today" deterministically


class ResolveIn(StrictModel):
    service: str = Field(min_length=1, max_length=120)
    engineer: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2000)
    root_cause: str = Field(min_length=1, max_length=2000)
    fix: str = Field(min_length=1, max_length=2000)
    did_not_work: str = Field(default="", max_length=2000)
    incident_id: str | None = Field(default=None, max_length=80)


class PrefIn(StrictModel):
    engineer: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=3, max_length=1000)


class PatternIn(StrictModel):
    question: str = Field(min_length=3, max_length=500)


class RateLimiter:
    """In-process sliding window. Protects the LLM budget on a small deployment.

    Per instance only: with several workers each has its own window. That is
    acceptable for abuse damping, not for billing-grade quotas.
    """

    def __init__(self, limit: int, window_seconds: float = 60.0, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int:
        """Return 0 if allowed, else seconds to wait."""
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, int(self.window - (now - hits[0])) + 1)
            hits.append(now)
            return 0


def _client_key(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _fail(status: int, public_message: str, exc: Exception | None = None) -> HTTPException:
    """Log the real error server-side and return a body with no internals."""
    error_id = uuid.uuid4().hex[:12]
    if exc is not None:
        log.exception("request failed id=%s: %s", error_id, public_message, exc_info=exc)
    else:
        log.error("request failed id=%s: %s", error_id, public_message)
    return HTTPException(status, {"error": public_message, "id": error_id})


def create_app(agent: RecurrenceAgent | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if agent is None:
        agent = RecurrenceAgent(build_memory(settings), build_llm(settings))
        if settings.offline:
            seed(agent.memory)  # offline fake memory starts empty every run
    app = FastAPI(title="Recurrence", version="0.1.0")
    app.state.agent = agent
    app.state.settings = settings
    app.state.ask_limiter = RateLimiter(settings.ask_rate_per_min)
    data = load_data()

    def _now(s: str | None) -> datetime:
        if not s:
            return datetime.now().astimezone()
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            raise HTTPException(422, "now must be ISO 8601")

    def require_write_token(request: Request) -> None:
        if settings.write_token:
            supplied = request.headers.get("x-recurrence-token")
            if not supplied or not secrets.compare_digest(supplied, settings.write_token):
                raise HTTPException(401, {"error": "missing or invalid write token"})
            return
        if not settings.offline:
            raise HTTPException(503, {"error": "writes disabled: RECURRENCE_WRITE_TOKEN is not configured"})

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/health")
    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "memory": agent.memory.name,
            "llm": agent.llm.name,
            "bank_id": settings.bank_id,
            "mode": "offline" if settings.offline else "live",
            "writes_enabled": settings.writes_enabled,
        }

    @app.get("/api/demo")
    def demo():
        return {
            "engineers": sorted({p["engineer"] for p in data["preferences"]}),
            "services": [s["service"] for s in data["service_facts"]],
            "alerts": data["demo_alerts"],
        }

    @app.post("/api/ask")
    def ask(body: AskIn, request: Request):
        wait = app.state.ask_limiter.check(_client_key(request, settings.trust_proxy))
        if wait:
            raise HTTPException(429, {"error": "rate limit reached, retry later", "retry_after_seconds": wait},
                                headers={"Retry-After": str(wait)})
        try:
            return agent.answer(body.alert, body.engineer, body.service, body.memory_on, _now(body.now))
        except HTTPException:
            raise
        except Exception as exc:
            raise _fail(502, "the page could not be answered", exc)

    @app.post("/api/resolve")
    def resolve(body: ResolveIn, request: Request):
        require_write_token(request)
        try:
            n = agent.resolve(**body.model_dump())
        except Exception as exc:
            raise _fail(502, "memory write failed", exc)
        return {"retained": n}

    @app.post("/api/preference")
    def preference(body: PrefIn, request: Request):
        require_write_token(request)
        try:
            agent.remember_preference(body.engineer, body.text)
        except Exception as exc:
            raise _fail(502, "memory write failed", exc)
        return {"retained": 1}

    @app.post("/api/patterns")
    def patterns(body: PatternIn):
        try:
            return {"answer": agent.patterns(body.question)}
        except Exception as exc:
            raise _fail(502, "reflect failed", exc)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
