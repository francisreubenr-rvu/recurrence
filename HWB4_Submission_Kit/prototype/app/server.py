"""FastAPI app: JSON API + a single-page console at /.

Run:  uvicorn app.server:app --reload --port 8000
Offline (no keys, fake memory, template answers):  RECURRENCE_OFFLINE=1 uvicorn app.server:app
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from recurrence.agent import RecurrenceAgent
from recurrence.config import Settings, build_llm, build_memory
from recurrence.seed import load_data, seed

STATIC = Path(__file__).parent / "static"


class AskIn(BaseModel):
    alert: str = Field(min_length=3)
    engineer: str
    service: str
    memory_on: bool = True
    now: str | None = None  # ISO time; lets the demo replay "today" deterministically


class ResolveIn(BaseModel):
    service: str
    engineer: str
    summary: str
    root_cause: str
    fix: str
    did_not_work: str = ""
    incident_id: str | None = None


class PrefIn(BaseModel):
    engineer: str
    text: str = Field(min_length=3)


class PatternIn(BaseModel):
    question: str = Field(min_length=3)


def create_app(agent: RecurrenceAgent | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if agent is None:
        agent = RecurrenceAgent(build_memory(settings), build_llm(settings))
        if settings.offline:
            seed(agent.memory)  # offline fake memory starts empty every run
    app = FastAPI(title="Recurrence", version="0.1.0")
    app.state.agent = agent
    data = load_data()

    def _now(s: str | None) -> datetime:
        if not s:
            return datetime.now().astimezone()
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            raise HTTPException(422, "now must be ISO 8601")

    @app.get("/health")
    @app.get("/api/health")
    def health():
        return {"ok": True, "memory": agent.memory.name, "llm": agent.llm.name, "bank_id": settings.bank_id}

    @app.get("/api/demo")
    def demo():
        return {
            "engineers": sorted({p["engineer"] for p in data["preferences"]}),
            "services": [s["service"] for s in data["service_facts"]],
            "alerts": data["demo_alerts"],
        }

    @app.post("/api/ask")
    def ask(body: AskIn):
        return agent.answer(body.alert, body.engineer, body.service, body.memory_on, _now(body.now))

    @app.post("/api/resolve")
    def resolve(body: ResolveIn):
        try:
            n = agent.resolve(**body.model_dump())
        except Exception as exc:
            raise HTTPException(502, f"memory write failed: {exc}")
        return {"retained": n}

    @app.post("/api/preference")
    def preference(body: PrefIn):
        try:
            agent.remember_preference(body.engineer, body.text)
        except Exception as exc:
            raise HTTPException(502, f"memory write failed: {exc}")
        return {"retained": 1}

    @app.post("/api/patterns")
    def patterns(body: PatternIn):
        try:
            return {"answer": agent.patterns(body.question)}
        except Exception as exc:
            raise HTTPException(502, f"reflect failed: {exc}")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
