"""Recurrence: the on-call agent that remembers every outage.

Flow for one page (memory ON):
  1. recall   - memories similar to the alert (past incidents, dead ends, service facts),
                with the agent's own past advice excluded
  2. recall   - this engineer's preferences (tag engineer:<slug>)
  3. recall   - prior advice for this service, bounded and kept in its own prompt section
  4. LLM      - Groq model answers with those memories in context; it may call
                recall_memory / reflect_on_history tools for more
  5. retain   - the advice given is retained as an experience, so the next page
                knows what was already tried
Later, POST /api/resolve retains the real outcome (root cause, fix, what failed).

Memory OFF skips 1-3 and 5 and gives the model no tools: the generic baseline.

Writes always use server time; the request ``now`` is a read-only replay anchor for
recall and display, so a replayed demo clock can never stamp a memory with a fake date.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Any

from .memory import MemoryHit, days_ago
from .seed import slug

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Search the team's incident memory (past incidents, fixes, failed fixes, service facts, engineer preferences). Does not return this assistant's own earlier advice.",
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

ADVICE_HEADING = "PRIOR ADVICE (unconfirmed, may have been wrong)"

# Only one of these may be set per recall call: the Hindsight server rejects a request
# that carries both. Incident recall therefore excludes advice with a tag group.
EXCLUDE_ADVICE = {"not": {"tags": ["kind:advice"], "match": "any_strict"}}


def _service_of(h: MemoryHit) -> str | None:
    if h.metadata.get("service"):
        return str(h.metadata["service"])
    for tag in h.tags:
        if tag.startswith("service:"):
            return tag.split(":", 1)[1]
    return None


def _label(h: MemoryHit, now: datetime) -> str:
    """Label one recalled memory so the model can tell an incident from a dead end from a service fact."""
    kind = str(h.metadata.get("kind") or h.type or "memory").lower()
    ref = ""
    if kind in ("incident", "dead-end"):
        ref = str(h.metadata.get("incident_id") or h.document_id or "")
    elif kind in ("service", "advice"):
        svc = _service_of(h)
        ref = f"service:{svc}" if svc else str(h.document_id or "")
    head = f"{kind.replace('-', ' ').upper()} {ref}".strip()
    d = days_ago(h.occurred_at, now)
    when = f"{d} days ago" if d is not None else None
    return "[" + ", ".join(p for p in (head, when) if p) + "]"


def _fmt_hits(hits: list[MemoryHit], now: datetime) -> str:
    return "\n".join(f"- {_label(h, now)} {h.text}" for h in hits)


def _dedupe_advice(hits: list[MemoryHit], cap: int = 3) -> list[MemoryHit]:
    """Prior advice repeats itself across pages; keep the first of each distinct text."""
    seen: set[str] = set()
    out: list[MemoryHit] = []
    for h in hits:
        key = " ".join(h.text.lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= cap:
            break
    return out


class RecurrenceAgent:
    def __init__(self, memory, llm):
        self.memory = memory
        self.llm = llm

    # ---- tools exposed to the model -------------------------------------------------
    def _execute(self, name: str, args: dict[str, Any]) -> str:
        if name == "recall_memory":
            groups: list[dict[str, Any]] = [EXCLUDE_ADVICE]
            if args.get("service"):
                groups.append({"tags": [f"service:{args['service']}"], "match": "any_strict"})
            hits = self.memory.recall(args["query"], tag_groups=groups, max_tokens=1500)
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
        advice_hits: list[MemoryHit] = []
        memory_errors: list[str] = []

        if memory_on:
            try:
                incident_hits = self.memory.recall(
                    f"{service}: {alert}",
                    # tag_groups only: this call must never carry tags as well, and it must
                    # never return the agent's own advice in place of a real postmortem.
                    tag_groups=[EXCLUDE_ADVICE],
                    max_tokens=2500,
                    query_timestamp=now.isoformat(),
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
            try:
                advice_hits = _dedupe_advice(
                    self.memory.recall(
                        f"What did Recurrence previously advise for {service} pages?",
                        tags=[f"service:{service}", "kind:advice"],
                        tags_match="all_strict",
                        max_tokens=500,
                        budget="low",
                        query_timestamp=now.isoformat(),
                    )
                )
            except Exception as exc:
                memory_errors.append(f"recall(prior advice) failed: {exc}")

        system = BASE_SYSTEM
        if memory_on and (incident_hits or pref_hits or advice_hits):
            system += (
                f"\n\nThe engineer on call is {engineer}. Current time: {now.isoformat(timespec='minutes')}."
                "\nUse the memories below. If one matches, say which incident it repeats and how many days ago."
                " List any fix that did NOT work so the engineer skips it."
                f"\n\nENGINEER PREFERENCES\n{_fmt_hits(pref_hits, now) or '- none recorded'}"
                f"\n\n{ADVICE_HEADING}\n"
                "What this assistant itself suggested on earlier pages. It is NOT a confirmed fix"
                " and it may have been wrong: use it as a lead only, never as evidence.\n"
                f"{_fmt_hits(advice_hits, now) or '- none recorded'}"
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

        # Nothing from a failed or empty answer is worth remembering as advice.
        llm_down = any(t.get("event") == "llm_unavailable" for t in trace)
        if memory_on and text.strip() and not llm_down:
            stamped = datetime.now().astimezone()  # server time: `now` is a replay anchor, not the clock
            try:
                self.memory.retain(
                    f"On {stamped.isoformat(timespec='minutes')} Recurrence advised {engineer} on a {service} page "
                    f"('{alert.splitlines()[0][:160]}'). Advice given: {text[:700]}",
                    context="advice given by the on-call agent (not yet confirmed as the fix)",
                    timestamp=stamped.isoformat(),
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
            "prior_advice": [dict(h.to_dict(), days_ago=days_ago(h.occurred_at, now)) for h in advice_hits],
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
        """Retain the confirmed outcome of a page. Returns number of memories written.

        ``now`` is accepted for API compatibility only: a write is stamped with server
        time, and the generated incident ID carries seconds plus two random hex chars so
        two resolves in the same minute can never collide.
        """
        stamped = datetime.now().astimezone()
        inc = incident_id or f"INC-LIVE-{stamped.strftime('%m%d%H%M%S')}-{secrets.token_hex(1)}"
        tags = [f"service:{service}", f"engineer:{slug(engineer)}"]
        items = [
            {
                "content": (
                    f"Incident {inc} on {service}, {stamped.isoformat(timespec='minutes')}, on-call {engineer}: {summary}\n"
                    f"Root cause: {root_cause}\nFix that worked: {fix}"
                ),
                "timestamp": stamped.isoformat(),
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
                    "timestamp": stamped.isoformat(),
                    "context": f"failed remediation attempt on {service}",
                    "document_id": f"{inc}-dead-end",
                    "tags": tags + ["kind:dead-end"],
                    "metadata": {"incident_id": inc, "service": service, "kind": "dead-end"},
                }
            )
        self.memory.retain_many(items)
        return len(items)

    def remember_preference(self, engineer: str, text: str, now: datetime | None = None) -> None:
        """``now`` is accepted for API compatibility only; the write is stamped with server time."""
        self.memory.retain(
            f"{engineer}: {text}",
            context="engineer preference stated to the on-call agent",
            timestamp=datetime.now().astimezone().isoformat(),
            tags=[f"engineer:{slug(engineer)}", "kind:preference"],
            metadata={"engineer": engineer, "kind": "preference"},
        )

    def patterns(self, question: str) -> str:
        return self.memory.reflect(question)
