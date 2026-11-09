"""Turn real paging-system webhooks into the one page shape the agent understands.

Two sources are supported, both as *push* payloads:

* Alertmanager (Prometheus Alertmanager v4 webhook, ``POST`` body with an
  ``alerts`` list). Configure a ``webhook_config`` receiver pointed at
  ``/api/ingest/alertmanager``.
* PagerDuty (v3 webhook, ``event`` envelope). Subscribe the endpoint to
  ``incident.triggered`` / ``incident.resolved``.

Nothing here invents data. A field the source did not send stays empty, and the
normaliser reports which fields it could not fill so the caller can decide.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Labels that a real alert usually carries; the first present one wins.
SERVICE_LABELS = ("service", "app", "job", "deployment", "container")
ENGINEER_LABELS = ("engineer", "oncall", "on_call", "owner", "team")

_RESOLVED = {"resolved", "ok", "recovered", "closed"}
_FIRING = {"firing", "triggered", "open", "critical", "warning", "error"}


class IngestError(ValueError):
    """The payload is not a shape we can normalise. Message is safe to return."""


@dataclass
class Page:
    """One normalised page, ready to hand to ``RecurrenceAgent.answer``."""

    source: str
    dedupe_key: str
    status: str
    alert: str
    service: str = ""
    engineer: str = ""
    starts_at: str | None = None
    url: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    @property
    def firing(self) -> bool:
        return self.status == "firing"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "alert": self.alert,
            "service": self.service,
            "engineer": self.engineer,
            "starts_at": self.starts_at,
            "url": self.url,
            "labels": self.labels,
            "missing": self.missing,
        }


def _first_label(labels: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = (labels.get(name) or "").strip()
        if value:
            return value
    return ""


def _status(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text in _RESOLVED:
        return "resolved"
    if text in _FIRING:
        return "firing"
    # Unknown status is kept verbatim rather than guessed at.
    return text or "unknown"


def _key(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]


def _compose(title: str, description: str, summary: str) -> str:
    """One alert string, with the noisy duplicate summary suppressed."""
    parts: list[str] = []
    for text in (title, summary, description):
        text = " ".join((text or "").split())
        if text and text not in parts:
            parts.append(text)
    if not parts:
        raise IngestError("the payload contains no alert title or description")
    return "\n".join(parts)[:4000]


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def normalize_alertmanager(payload: dict) -> list[Page]:
    """Alertmanager v4 webhook. One Page per entry in ``alerts``."""
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise IngestError("expected an 'alerts' list (Alertmanager v4 webhook)")
    pages: list[Page] = []
    for raw in alerts:
        if not isinstance(raw, dict):
            raise IngestError("every entry in 'alerts' must be an object")
        labels = {str(k): str(v) for k, v in (raw.get("labels") or {}).items()}
        annotations = {str(k): str(v) for k, v in (raw.get("annotations") or {}).items()}
        title = annotations.get("summary") or labels.get("alertname") or ""
        description = annotations.get("description") or annotations.get("message") or ""
        alert = _compose(title, description, annotations.get("runbook", ""))
        service = _first_label(labels, SERVICE_LABELS)
        engineer = _first_label(labels, ENGINEER_LABELS)
        status = _status(raw.get("status") or payload.get("status") or "")
        fingerprint = str(raw.get("fingerprint") or "")
        pages.append(
            Page(
                source="alertmanager",
                dedupe_key=fingerprint or _key(service, alert, status),
                status=status,
                alert=alert,
                service=service,
                engineer=engineer,
                starts_at=_iso(raw.get("startsAt")),
                url=str(raw.get("generatorURL") or payload.get("externalURL") or ""),
                labels=labels,
                missing=[name for name, value in (("service", service), ("engineer", engineer)) if not value],
            )
        )
    return pages


def normalize_pagerduty(payload: dict) -> list[Page]:
    """PagerDuty v3 webhook. Only incident events carry a page."""
    event = payload.get("event")
    if not isinstance(event, dict):
        raise IngestError("expected an 'event' object (PagerDuty v3 webhook)")
    event_type = str(event.get("event_type") or "")
    data = event.get("data")
    if not isinstance(data, dict):
        raise IngestError("expected 'event.data' to be an incident object")
    raw_status = event_type.split(".")[-1] or data.get("status") or ""
    status = _status(raw_status)
    if status == "triggered":
        status = "firing"
    title = str(data.get("title") or data.get("summary") or "")
    service_obj = data.get("service")
    service = ""
    if isinstance(service_obj, dict):
        service = str(service_obj.get("summary") or service_obj.get("id") or "")
    elif service_obj:
        service = str(service_obj)
    details = data.get("body") if isinstance(data.get("body"), dict) else {}
    description = str(details.get("details") or data.get("description") or "")
    alert = _compose(title, description, "")
    incident_id = str(data.get("id") or "")
    engineer = _first_label({str(k): str(v) for k, v in (data.get("custom_details") or {}).items()}, ENGINEER_LABELS)
    return [
        Page(
            source="pagerduty",
            dedupe_key=incident_id or _key(service, alert, status),
            status=status,
            alert=alert,
            service=service,
            engineer=engineer,
            starts_at=_iso(data.get("created_at")),
            url=str(data.get("html_url") or ""),
            labels={"urgency": str(data.get("urgency") or "")},
            missing=[name for name, value in (("service", service), ("engineer", engineer)) if not value],
        )
    ]


NORMALIZERS = {
    "alertmanager": normalize_alertmanager,
    "pagerduty": normalize_pagerduty,
}


class DedupeStore:
    """In-process dedupe window, keyed on the source fingerprint.

    Alertmanager re-sends the same alert every ``repeat_interval`` and every
    receiver retry. Dedupe keeps one page from becoming ten identical answers.
    Per instance only, so it damps repeats rather than guaranteeing exactly-once.
    """

    def __init__(self, ttl_seconds: float = 300.0, clock=time.monotonic):
        self.ttl = ttl_seconds
        self.clock = clock
        self._seen: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (is_duplicate, times_seen_including_this_one)."""
        now = self.clock()
        with self._lock:
            for stale in [k for k, (at, _) in self._seen.items() if now - at >= self.ttl]:
                del self._seen[stale]
            previous = self._seen.get(key)
            if previous is None:
                self._seen[key] = (now, 1)
                return False, 1
            at, count = previous
            self._seen[key] = (at, count + 1)
            return True, count + 1
