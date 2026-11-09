import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.server import create_app
from recurrence.config import Settings
from recurrence.seed import load_data


def make_settings(**overrides):
    base = Settings.from_env(offline=True)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def client(**overrides):
    return TestClient(create_app(settings=make_settings(**overrides)))


def test_health_offline():
    c = client()
    for path in ("/health", "/api/health"):
        r = c.get(path)
        assert r.status_code == 200
        body = r.json()
        assert body["memory"] == "fake-offline" and body["llm"] == "offline-template"
        assert body["mode"] == "offline" and body["writes_enabled"] is True


def test_ask_memory_on_and_off():
    c = client()
    a = load_data()["demo_alerts"][0]
    body = {"alert": a["alert"], "engineer": a["engineer"], "service": a["service"], "now": a["now"]}
    on = c.post("/api/ask", json=body).json()
    off = c.post("/api/ask", json={**body, "memory_on": False}).json()
    assert on["memories"] and any(i in on["answer"] for i in a["expected_incident_ids"])
    assert off["memories"] == [] and not any(i in off["answer"] for i in a["expected_incident_ids"])


def test_ask_validation_and_bad_time():
    c = client()
    assert c.post("/api/ask", json={"alert": "x", "engineer": "a", "service": "b"}).status_code == 422
    r = c.post("/api/ask", json={"alert": "5xx spike", "engineer": "a", "service": "b", "now": "yesterday"})
    assert r.status_code == 422


def test_input_bounds_reject_oversize_and_blank():
    c = client()
    assert c.post("/api/ask", json={"alert": "x" * 9000, "engineer": "a", "service": "b"}).status_code == 422
    assert c.post("/api/ask", json={"alert": "5xx spike", "engineer": "   ", "service": "b"}).status_code == 422
    assert c.post("/api/resolve", json={"service": "s", "engineer": "e", "summary": "", "root_cause": "y", "fix": "z"}).status_code == 422
    assert c.post("/api/preference", json={"engineer": "e", "text": "x" * 1001}).status_code == 422
    assert c.post("/api/patterns", json={"question": "x" * 501}).status_code == 422


def test_writes_require_token_when_configured():
    c = client(write_token="s3cret")
    body = {"service": "s", "engineer": "e", "summary": "x", "root_cause": "y", "fix": "z"}
    assert c.post("/api/resolve", json=body).status_code == 401
    assert c.post("/api/resolve", json=body, headers={"X-Recurrence-Token": "wrong"}).status_code == 401
    assert c.post("/api/resolve", json=body, headers={"X-Recurrence-Token": "s3cret"}).json() == {"retained": 1}
    pref = {"engineer": "e", "text": "rollback first"}
    assert c.post("/api/preference", json=pref).status_code == 401
    assert c.post("/api/preference", json=pref, headers={"X-Recurrence-Token": "s3cret"}).status_code == 200


def test_live_mode_without_token_disables_writes():
    from recurrence.llm import OfflineLLM
    from recurrence.memory import FakeMemory
    from recurrence.agent import RecurrenceAgent

    settings = make_settings(offline=False, write_token=None)
    agent = RecurrenceAgent(FakeMemory(), OfflineLLM())
    c = TestClient(create_app(agent=agent, settings=settings))
    assert c.get("/api/health").json()["writes_enabled"] is False
    body = {"service": "s", "engineer": "e", "summary": "x", "root_cause": "y", "fix": "z"}
    r = c.post("/api/resolve", json=body)
    assert r.status_code == 503 and "RECURRENCE_WRITE_TOKEN" in r.json()["detail"]["error"]


def test_backend_errors_are_redacted_and_logged(caplog):
    class Broken:
        name = "broken-memory"

        def resolve(self, **kwargs):
            raise RuntimeError("SECRET internal host db-prod-7")

        def remember_preference(self, *a, **k):
            raise RuntimeError("SECRET internal host db-prod-7")

        def patterns(self, *a, **k):
            raise RuntimeError("SECRET internal host db-prod-7")

    from recurrence.llm import OfflineLLM
    from recurrence.memory import FakeMemory

    agent = SimpleNamespace(
        memory=FakeMemory(), llm=OfflineLLM(),
        resolve=Broken().resolve, remember_preference=Broken().remember_preference,
        patterns=Broken().patterns, answer=lambda *a, **k: {},
    )
    c = TestClient(create_app(agent=agent, settings=make_settings()))
    with caplog.at_level(logging.ERROR, logger="recurrence.server"):
        r = c.post("/api/resolve", json={"service": "s", "engineer": "e", "summary": "x", "root_cause": "y", "fix": "z"})
    assert r.status_code == 502
    assert "SECRET" not in r.text
    assert r.json()["detail"]["error"] == "memory write failed"
    assert r.json()["detail"]["id"]
    assert "SECRET" in caplog.text


def test_security_headers_present():
    c = client()
    r = c.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


def test_ask_is_rate_limited():
    c = client(ask_rate_per_min=2)
    body = {"alert": "5xx spike", "engineer": "Arjun Mehta", "service": "payments-api"}
    assert c.post("/api/ask", json=body).status_code == 200
    assert c.post("/api/ask", json=body).status_code == 200
    r = c.post("/api/ask", json=body)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_resolve_preference_patterns_demo_index():
    c = client()
    assert c.post("/api/resolve", json={"service": "s", "engineer": "e", "summary": "x", "root_cause": "y", "fix": "z"}).json() == {"retained": 1}
    assert c.post("/api/preference", json={"engineer": "e", "text": "rollback-first please"}).json() == {"retained": 1}
    assert "answer" in c.post("/api/patterns", json={"question": "what repeats?"}).json()
    assert c.get("/api/demo").json()["alerts"]
    assert c.get("/").status_code == 200


def test_static_app_js_served():
    c = client()
    r = c.get("/static/app.js")
    assert r.status_code == 200 and "describeMemory" in r.text
