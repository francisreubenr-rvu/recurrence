"""Alertmanager and PagerDuty webhook normalisation, dedupe, and the ingest route.

Payload shapes are taken from the two systems' documented webhook formats. No
fixture here is presented as a real production page; they are protocol examples.
"""
import pytest

from fastapi.testclient import TestClient

from app.server import create_app
from recurrence.config import Settings
from recurrence.ingest import DedupeStore, IngestError, normalize_alertmanager, normalize_pagerduty


def make_settings(**overrides):
    base = Settings.from_env(offline=True)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def client(**overrides):
    return TestClient(create_app(settings=make_settings(**overrides)))


ALERTMANAGER = {
    "version": "4",
    "status": "firing",
    "receiver": "recurrence",
    "externalURL": "http://alertmanager.internal:9093",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighErrorRate",
                "service": "payments-api",
                "engineer": "Arjun Mehta",
                "severity": "critical",
            },
            "annotations": {
                "summary": "payments-api 5xx above 15% for 5m",
                "description": "HikariPool-1 - Connection is not available (total=40, active=40, waiting=190)",
            },
            "startsAt": "2026-11-09T19:50:00+05:30",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus.internal/graph?g0.expr=high_error_rate",
            "fingerprint": "1f9d0a5a4c3b2e10",
        }
    ],
}

PAGERDUTY = {
    "event": {
        "id": "evt-1",
        "event_type": "incident.triggered",
        "data": {
            "id": "P1234",
            "title": "High latency on ledger-api",
            "status": "triggered",
            "urgency": "high",
            "created_at": "2026-11-09T14:20:00Z",
            "html_url": "https://example.pagerduty.com/incidents/P1234",
            "service": {"summary": "ledger-api"},
            "custom_details": {"oncall": "Priya Nair", "p99_ms": "4200"},
        },
    }
}


# ---- normaliser unit tests -------------------------------------------------------


def test_alertmanager_alert_becomes_one_page():
    (page,) = normalize_alertmanager(ALERTMANAGER)
    assert page.source == "alertmanager" and page.firing
    assert page.service == "payments-api"
    assert page.engineer == "Arjun Mehta"
    assert "payments-api 5xx above 15% for 5m" in page.alert
    assert "HikariPool-1" in page.alert
    assert page.starts_at == "2026-11-09T19:50:00+05:30"
    assert page.dedupe_key == "1f9d0a5a4c3b2e10"
    assert page.missing == []


def test_alertmanager_reports_fields_the_payload_did_not_send():
    payload = {"alerts": [{"status": "firing", "labels": {"alertname": "DiskFull"}}]}
    (page,) = normalize_alertmanager(payload)
    assert page.service == "" and page.engineer == ""
    assert page.missing == ["service", "engineer"]


def test_alertmanager_resolved_alert_is_not_a_firing_page():
    payload = {"alerts": [{**ALERTMANAGER["alerts"][0], "status": "resolved"}]}
    (page,) = normalize_alertmanager(payload)
    assert page.status == "resolved" and not page.firing


def test_alertmanager_rejects_a_payload_without_alerts():
    with pytest.raises(IngestError, match="alerts"):
        normalize_alertmanager({"status": "firing"})


def test_pagerduty_triggered_normalises_to_firing():
    (page,) = normalize_pagerduty(PAGERDUTY)
    assert page.source == "pagerduty" and page.firing
    assert page.service == "ledger-api"
    assert page.engineer == "Priya Nair"
    assert page.alert == "High latency on ledger-api"
    assert page.dedupe_key == "P1234"
    assert page.url.endswith("/P1234")


def test_pagerduty_requires_an_event_envelope():
    with pytest.raises(IngestError, match="event"):
        normalize_pagerduty({"messages": []})


# ---- dedupe ----------------------------------------------------------------------


def test_dedupe_window_marks_repeats_and_expires():
    now = [0.0]
    store = DedupeStore(ttl_seconds=60.0, clock=lambda: now[0])
    assert store.check("a") == (False, 1)
    assert store.check("a") == (True, 2)
    now[0] = 61.0
    assert store.check("a") == (False, 1)


def test_dedupe_evicts_expired_entries():
    now = [0.0]
    store = DedupeStore(ttl_seconds=10.0, clock=lambda: now[0])
    for i in range(50):
        store.check(f"key-{i}")
    now[0] = 11.0
    store.check("fresh")
    assert len(store._seen) == 1


# ---- route -----------------------------------------------------------------------


def test_ingest_alertmanager_returns_normalised_pages():
    c = client()
    r = c.post("/api/ingest/alertmanager", json=ALERTMANAGER)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "alertmanager"
    assert body["accepted"] == 1 and body["duplicates"] == 0
    page = body["pages"][0]
    assert page["status"] == "firing" and page["duplicate"] is False
    assert page["service"] == "payments-api"
    assert "answer" not in page  # answering is opt-in


def test_ingest_marks_a_repeated_delivery_and_keeps_status():
    c = client()
    first = c.post("/api/ingest/alertmanager", json=ALERTMANAGER).json()
    second = c.post("/api/ingest/alertmanager", json=ALERTMANAGER).json()
    assert first["duplicates"] == 0 and second["duplicates"] == 1
    page = second["pages"][0]
    assert page["duplicate"] is True and page["seen_count"] == 2


def test_ingest_can_answer_the_page_inline():
    c = client()
    r = c.post("/api/ingest/alertmanager?answer=true", json=ALERTMANAGER)
    assert r.status_code == 200
    page = r.json()["pages"][0]
    assert page["answer"]["memory_on"] is True
    assert page["answer"]["memories"]


def test_ingest_does_not_answer_a_resolved_alert_or_a_repeat():
    c = client()
    resolved = {"alerts": [{**ALERTMANAGER["alerts"][0], "status": "resolved"}]}
    assert "answer" not in c.post("/api/ingest/alertmanager?answer=true", json=resolved).json()["pages"][0]
    c.post("/api/ingest/alertmanager?answer=true", json=ALERTMANAGER)
    repeat = c.post("/api/ingest/alertmanager?answer=true", json=ALERTMANAGER).json()["pages"][0]
    assert "answer" not in repeat and repeat["duplicate"] is True


def test_ingest_skips_a_page_with_no_engineer_and_says_why():
    payload = {"alerts": [{"status": "firing", "labels": {"alertname": "DiskFull", "service": "ledger-api"},
                           "annotations": {"summary": "ledger-api disk 94% full"}}]}
    page = client().post("/api/ingest/alertmanager?answer=true", json=payload).json()["pages"][0]
    assert "answer" not in page
    assert "no engineer" in page["skipped"]


def test_ingest_accepts_pagerduty():
    body = client().post("/api/ingest/pagerduty", json=PAGERDUTY).json()
    assert body["source"] == "pagerduty"
    assert body["pages"][0]["service"] == "ledger-api"


def test_ingest_rejects_an_unknown_source_and_a_bad_payload():
    c = client()
    assert c.post("/api/ingest/datadog", json={"alerts": []}).status_code == 404
    r = c.post("/api/ingest/alertmanager", json={"nope": True})
    assert r.status_code == 422 and "alerts" in r.json()["detail"]["error"]


def test_ingest_requires_the_write_token_when_configured():
    c = client(write_token="s3cret")
    assert c.post("/api/ingest/alertmanager", json=ALERTMANAGER).status_code == 401
    assert c.post("/api/ingest/alertmanager", json=ALERTMANAGER,
                  headers={"X-Recurrence-Token": "s3cret"}).status_code == 200
