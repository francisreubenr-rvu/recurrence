from fastapi.testclient import TestClient

from app.server import create_app
from recurrence.config import Settings
from recurrence.seed import load_data


def client():
    return TestClient(create_app(settings=Settings.from_env(offline=True)))


def test_health_offline():
    c = client()
    for path in ("/health", "/api/health"):
        r = c.get(path)
        assert r.status_code == 200
        assert r.json()["memory"] == "fake-offline" and r.json()["llm"] == "offline-template"


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


def test_resolve_preference_patterns_demo_index():
    c = client()
    assert c.post("/api/resolve", json={"service": "s", "engineer": "e", "summary": "x", "root_cause": "y", "fix": "z"}).json() == {"retained": 1}
    assert c.post("/api/preference", json={"engineer": "e", "text": "rollback-first please"}).json() == {"retained": 1}
    assert "answer" in c.post("/api/patterns", json={"question": "what repeats?"}).json()
    assert c.get("/api/demo").json()["alerts"]
    assert c.get("/").status_code == 200


def test_state_reports_the_memories_this_process_holds():
    c = client()
    body = c.get("/api/state").json()
    assert body["memory"] == "fake-offline" and body["mode"] == "offline"
    assert body["process_state"] is True and body["memories_held"] >= 31


def test_admin_reset_restores_the_seeded_demo_store():
    c = client()
    before = c.get("/api/state").json()["memories_held"]
    c.post("/api/ask", json={"alert": "5xx spike on payments-api", "engineer": "Arjun Mehta", "service": "payments-api"})
    assert c.get("/api/state").json()["memories_held"] == before + 1  # the advice write
    reset = c.post("/api/admin/reset").json()
    assert reset["seeded"] == 31 and reset["memories_held"] == 31


def test_admin_reset_refuses_a_live_bank():
    from recurrence.agent import RecurrenceAgent
    from recurrence.config import Settings as S
    from recurrence.llm import OfflineLLM
    from recurrence.memory import FakeMemory

    settings = S.from_env(offline=True)
    settings.offline = False  # live mode, but a fake store so the test needs no keys
    c = TestClient(create_app(agent=RecurrenceAgent(FakeMemory(), OfflineLLM()), settings=settings))
    r = c.post("/api/admin/reset")
    assert r.status_code == 409 and "offline demo mode" in r.json()["detail"]
