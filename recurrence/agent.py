"""Recurrence: the on-call agent that remembers every outage.

Flow for one page (memory ON):
  1. recall   - memories similar to the alert (past incidents, dead ends, service facts)
  2. recall   - this engineer's preferences (tag engineer:<slug>)
  3. LLM      - Groq model answers with those memories in context; it may call
                recall_memory / reflect_on_history tools for more
  4. retain   - the advice given is retained as an experience, so the next page
                knows what was already tried
Later, POST /api/resolve retains the real outcome (root cause, fix, what failed).

Memory OFF skips 1, 2 and 4 and gives the model no tools: the generic baseline.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .memory import MemoryHit, days_ago
from .seed import slug

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Search the team's incident memory (past incidents, fixes, failed fixes, service facts, engineer preferences).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for, e.g. an error string or service name"},
                    "service": {"type": "string", "description": "Optional service name to scope the search"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reflect_on_history",
            "description": "Ask the memory bank to reason over all past incidents, e.g. 'what pattern links ledger-svc deploys to payments-api errors?'",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
]

BASE_SYSTEM = (
    "You are Recurrence, an on-call assistant for a payments company's SRE team. "
    "Answer the page in under 200 words. Lead with the single most likely mitigation. "
    "Give exact commands where you can. Never invent incident IDs."
)


def _fmt_hits(hits: list[MemoryHit], now: datetime) -> str:
    rows = []
    for h in hits:
        d = days_ago(h.occurred_at, now)
        when = f"{d} days ago" if d is not None else "date unknown"
        rows.append(f"- ({when}) {h.text}")
    return "\n".join(rows)


class RecurrenceAgent:
    def __init__(self, memory, llm):
        self.memory = memory
        self.llm = llm

    # ---- tools exposed to the model -------------------------------------------------
    def _execute(self, name: str, args: dict[str, Any]) -> str:
        if name == "recall_memory":
            tags = [f"service:{args['service']}"] if args.get("service") else None
            hits = self.memory.recall(args["query"], tags=tags, max_tokens=1500)
            return json.dumps([h.to_dict() for h in hits[:6]], default=str)
        if name == "reflect_on_history":
            return json.dumps({"answer": self.memory.reflect(args["question"])})
        raise KeyError(name)

    # ---- main entry -----------------------------------------------------------------
    def answer(
        self,
        alert: str,
        engineer: str,
        service: str,
        memory_on: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now().astimezone()
        incident_hits: list[MemoryHit] = []
        pref_hits: list[MemoryHit] = []
        memory_errors: list[str] = []

        if memory_on:
            try:
                incident_hits = self.memory.recall(
                    f"{service}: {alert}", max_tokens=2500, query_timestamp=now.isoformat()
                )
            except Exception as exc:  # memory down must not block the page
                memory_errors.append(f"recall(incidents) failed: {exc}")
            try:
                pref_hits = self.memory.recall(
                    f"How does {engineer} prefer to receive help during incidents?",
                    # "all": incidents also carry the engineer tag; only want their preferences
                    tags=[f"engineer:{slug(engineer)}", "kind:preference"],
                    tags_match="all_strict",
                    max_tokens=600,
                    query_timestamp=now.isoformat(),
                )
            except Exception as exc:
                memory_errors.append(f"recall(preferences) failed: {exc}")

        system = BASE_SYSTEM
        if memory_on and (incident_hits or pref_hits):
            system += (
                f"\n\nThe engineer on call is {engineer}. Current time: {now.isoformat(timespec='minutes')}."
                "\nUse the memories below. If one matches, say which incident it repeats and how many days ago."
                " List any fix that did NOT work so the engineer skips it."
                f"\n\nENGINEER PREFERENCES\n{_fmt_hits(pref_hits, now) or '- none recorded'}"
                f"\n\nPAST INCIDENT MEMORIES\n{_fmt_hits(incident_hits, now)}"
            )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Service: {service}\nPage:\n{alert}"},
        ]
        tools = TOOLS if memory_on else None
        try:
            text, trace = self.llm.run(messages, tools, self._execute)
        except Exception as exc:  # LLM fully down: still show the recalled memories
            text, trace = (
                "The language model is unreachable right now. The recalled memories on the right are the best lead.",
                [{"event": "llm_unavailable", "detail": str(exc)[:200]}],
            )

        if memory_on:
            try:
                self.memory.retain(
                    f"On {now.isoformat(timespec='minutes')} Recurrence advised {engineer} on a {service} page "
                    f"('{alert.splitlines()[0][:160]}'). Advice given: {text[:700]}",
                    context="advice given by the on-call agent (not yet confirmed as the fix)",
                    timestamp=now.isoformat(),
                    tags=[f"service:{service}", f"engineer:{slug(engineer)}", "kind:advice"],
                    metadata={"kind": "advice", "service": service, "engineer": engineer},
                )
            except Exception as exc:
                memory_errors.append(f"retain(advice) failed: {exc}")

        return {
            "answer": text,
            "memory_on": memory_on,
            "memories": [dict(h.to_dict(), days_ago=days_ago(h.occurred_at, now)) for h in incident_hits],
            "preferences": [dict(h.to_dict(), days_ago=days_ago(h.occurred_at, now)) for h in pref_hits],
            "tool_trace": trace,
            "memory_errors": memory_errors,
            "backend": {"memory": getattr(self.memory, "name", "?"), "llm": getattr(self.llm, "name", "?")},
        }

    def resolve(
        self,
        service: str,
        engineer: str,
        summary: str,
        root_cause: str,
        fix: str,
        did_not_work: str = "",
        incident_id: str | None = None,
        now: datetime | None = None,
    ) -> int:
        """Retain the confirmed outcome of a page. Returns number of memories written."""
        now = now or datetime.now().astimezone()
        inc = incident_id or f"INC-LIVE-{now.strftime('%m%d%H%M')}"
        tags = [f"service:{service}", f"engineer:{slug(engineer)}"]
        items = [
            {
                "content": (
                    f"Incident {inc} on {service}, {now.isoformat(timespec='minutes')}, on-call {engineer}: {summary}\n"
                    f"Root cause: {root_cause}\nFix that worked: {fix}"
                ),
                "timestamp": now.isoformat(),
                "context": f"resolved incident postmortem for {service}",
                "document_id": inc,
                "tags": tags + ["kind:incident"],
                "metadata": {"incident_id": inc, "service": service, "kind": "incident"},
            }
        ]
        if did_not_work.strip():
            items.append(
                {
                    "content": f"During {inc} on {service} this did NOT work and should not be repeated: {did_not_work}",
                    "timestamp": now.isoformat(),
                    "context": f"failed remediation attempt on {service}",
                    "document_id": f"{inc}-dead-end",
                    "tags": tags + ["kind:dead-end"],
                    "metadata": {"incident_id": inc, "service": service, "kind": "dead-end"},
                }
            )
        self.memory.retain_many(items)
        return len(items)

    def remember_preference(self, engineer: str, text: str, now: datetime | None = None) -> None:
        now = now or datetime.now().astimezone()
        self.memory.retain(
            f"{engineer}: {text}",
            context="engineer preference stated to the on-call agent",
            timestamp=now.isoformat(),
            tags=[f"engineer:{slug(engineer)}", "kind:preference"],
            metadata={"engineer": engineer, "kind": "preference"},
        )

    def patterns(self, question: str) -> str:
        return self.memory.reflect(question)
