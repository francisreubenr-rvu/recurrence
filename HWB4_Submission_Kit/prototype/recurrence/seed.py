"""Turn the synthetic incident history into Hindsight memories.

Run:  python -m recurrence.seed            (uses .env: Hindsight server)
      python -m recurrence.seed --offline  (FakeMemory, just prints counts)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "data" / "incidents.json"


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")



def load_data(path: Path = DATA) -> dict[str, Any]:
    return json.loads(path.read_text())


def incident_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """One retain item per incident narrative, plus one per 'dead end'.

    Dead ends are stored separately on purpose: "what NOT to do" is the memory
    a tired on-call engineer most needs at 8 pm, and a separate item makes it
    recallable on its own.
    """
    items: list[dict[str, Any]] = []
    for inc in data["incidents"]:
        base_tags = [f"service:{inc['service']}", f"engineer:{slug(inc['on_call'])}"]
        meta = {
            "incident_id": inc["id"],
            "service": inc["service"],
            "severity": inc["severity"],
            "on_call": inc["on_call"],
        }
        narrative = (
            f"Incident {inc['id']} ({inc['severity']}) on {inc['service']}, opened {inc['opened_at']}, "
            f"on-call {inc['on_call']}: {inc['title']}.\n"
            f"Alert: {inc['alert']}\n"
            f"Logs: {inc['log_excerpt']}\n"
            f"Root cause: {inc['root_cause']}\n"
            f"Fix that worked: {inc['fix']}\n"
            f"Time to mitigate: {inc['time_to_mitigate_min']} minutes."
        )
        items.append(
            {
                "content": narrative,
                "timestamp": inc["opened_at"],
                "context": f"resolved incident postmortem for {inc['service']}",
                "document_id": inc["id"],
                "tags": base_tags + ["kind:incident"],
                "metadata": {**meta, "kind": "incident"},
            }
        )
        if inc.get("did_not_work"):
            items.append(
                {
                    "content": (
                        f"During {inc['id']} on {inc['service']} this did NOT work and should not be repeated: "
                        f"{inc['did_not_work']}"
                    ),
                    "timestamp": inc["resolved_at"],
                    "context": f"failed remediation attempt on {inc['service']}",
                    "document_id": f"{inc['id']}-dead-end",
                    "tags": base_tags + ["kind:dead-end"],
                    "metadata": {**meta, "kind": "dead-end"},
                }
            )
    return items


def preference_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "content": p["text"],
            "timestamp": p["stated_at"],
            "context": "engineer preference stated in incident channel",
            "document_id": f"pref-{slug(p['engineer'])}-{i}",
            "tags": [f"engineer:{slug(p['engineer'])}", "kind:preference"],
            "metadata": {"engineer": p["engineer"], "kind": "preference"},
        }
        for i, p in enumerate(data["preferences"])
    ]


def service_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "content": s["text"],
            "context": "service catalog entry",
            "document_id": f"svc-{s['service']}",
            "tags": [f"service:{s['service']}", "kind:service"],
            "metadata": {"service": s["service"], "kind": "service"},
        }
        for s in data["service_facts"]
    ]


def all_items(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = data or load_data()
    return incident_items(data) + preference_items(data) + service_items(data)


def seed(memory, data: dict[str, Any] | None = None, batch_size: int = 8) -> int:
    items = all_items(data)
    memory.ensure_bank()
    for i in range(0, len(items), batch_size):
        memory.retain_many(items[i : i + batch_size])
    return len(items)


def main() -> None:
    from .config import Settings, build_memory

    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use the OFFLINE fake memory (no server)")
    args = ap.parse_args()
    settings = Settings.from_env(offline=args.offline)
    mem = build_memory(settings)
    n = seed(mem)
    print(f"Retained {n} memories into bank '{settings.bank_id}' via backend '{mem.name}'.")


if __name__ == "__main__":
    main()
