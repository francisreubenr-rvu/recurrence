"""Memory layer for Recurrence.

Two backends share one small interface:

* ``HindsightMemory`` - the real backend. Talks to a Hindsight server (self-hosted
  Docker or Hindsight Cloud) through the official ``hindsight-client`` package
  (``pip install hindsight-client``), using ``retain`` / ``retain_batch`` /
  ``recall`` / ``reflect`` exactly as documented at
  https://hindsight.vectorize.io/sdks/python

* ``FakeMemory`` - OFFLINE / TEST-ONLY stand-in. A naive keyword-overlap store
  that lets the unit tests and the offline smoke run work without a server or
  API keys. It does NOT reproduce Hindsight's fact extraction, entity graph,
  temporal retrieval, reranking or observations, and its results must never be
  presented as Hindsight results.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

log = logging.getLogger("recurrence.memory")

BANK_MISSION = (
    "I am the on-call memory for Tamarind Pay's SRE team. I remember every past "
    "incident: the alert, the logs, the root cause, the fix that worked, and the "
    "fixes that did NOT work. I also remember how each engineer likes to receive "
    "help and how each service is built. Prefer facts from resolved incidents over guesses."
)


@dataclass
class MemoryHit:
    """One recalled memory, normalised across backends for the UI and the LLM."""

    text: str
    type: str | None = None
    occurred_at: str | None = None
    tags: list[str] = field(default_factory=list)
    context: str | None = None
    document_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "type": self.type,
            "occurred_at": self.occurred_at,
            "tags": self.tags,
            "context": self.context,
            "document_id": self.document_id,
            "metadata": self.metadata,
        }


class MemoryBackend(Protocol):
    name: str

    def ensure_bank(self) -> None: ...

    def retain(
        self,
        content: str,
        *,
        context: str | None = None,
        timestamp: str | None = None,
        tags: list[str] | None = None,
        document_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None: ...

    def retain_many(self, items: list[dict[str, Any]]) -> None: ...

    def recall(
        self,
        query: str,
        *,
        tags: list[str] | None = None,
        max_tokens: int = 2048,
        budget: str = "mid",
        query_timestamp: str | None = None,
        tags_match: str = "any",
        tag_groups: list[dict] | None = None,
    ) -> list[MemoryHit]: ...

    def reflect(self, query: str, *, context: str | None = None, tags: list[str] | None = None) -> str: ...


# --------------------------------------------------------------------------------------
# Real backend: Hindsight
# --------------------------------------------------------------------------------------
class HindsightMemory:
    """Hindsight-backed memory. One bank per team; tags scope service/engineer/kind."""

    name = "hindsight"

    def __init__(self, base_url: str, bank_id: str, api_key: str | None = None, client: Any = None):
        if client is None:
            from hindsight_client import Hindsight  # official client

            client = Hindsight(base_url=base_url, api_key=api_key, timeout=60.0)
        self.client = client
        self.bank_id = bank_id

    def ensure_bank(self) -> None:
        try:
            self.client.create_bank(
                bank_id=self.bank_id,
                name="Recurrence on-call memory",
                mission=BANK_MISSION,
                # 1-5 scale per docs: skeptical (don't over-trust weak matches), literal (commands matter)
                disposition={"skepticism": 4, "literalism": 4, "empathy": 2},
            )
        except Exception as exc:  # bank already exists, or server older than this API
            log.info("create_bank skipped: %s", exc)

    def retain(self, content, *, context=None, timestamp=None, tags=None, document_id=None, metadata=None):
        self.client.retain(
            bank_id=self.bank_id,
            content=content,
            context=context,
            timestamp=timestamp,
            tags=tags,
            document_id=document_id,
            metadata=metadata,
        )

    def retain_many(self, items):
        # items: dicts with content (+ optional timestamp, context, metadata, document_id, tags)
        self.client.retain_batch(bank_id=self.bank_id, items=items)

    def recall(
        self,
        query,
        *,
        tags=None,
        max_tokens=2048,
        budget="mid",
        query_timestamp=None,
        tags_match="any",
        tag_groups=None,
    ):
        if tags and tag_groups:
            raise ValueError("pass either tags or tag_groups, not both: the server rejects that combination")
        # query_timestamp anchors relative time ("last week") to the page's time, which
        # matters when the demo replays a fixed "now".
        resp = self.client.recall(
            bank_id=self.bank_id,
            query=query,
            max_tokens=max_tokens,
            budget=budget,
            tags=tags,
            tags_match=tags_match,
            tag_groups=tag_groups,
            query_timestamp=query_timestamp,
        )
        hits: list[MemoryHit] = []
        for r in resp.results or []:
            occurred = r.occurred_start or r.mentioned_at
            hits.append(
                MemoryHit(
                    text=r.text,
                    type=r.type,
                    occurred_at=str(occurred) if occurred else None,
                    tags=list(r.tags or []),
                    context=r.context,
                    document_id=r.document_id,
                    metadata=dict(r.metadata or {}),
                )
            )
        return hits

    def reflect(self, query, *, context=None, tags=None):
        resp = self.client.reflect(bank_id=self.bank_id, query=query, budget="low", context=context, tags=tags)
        return resp.text or ""


# --------------------------------------------------------------------------------------
# OFFLINE / TEST-ONLY backend
# --------------------------------------------------------------------------------------
_WORD = re.compile(r"[a-z0-9][a-z0-9_\-\.]{1,}")
_STOP = set("the a an and or of to in on for is was with at by from as it this that be not no".split())


def _tokens(text: str) -> list[str]:
    return [t.strip(".-") for t in _WORD.findall(text.lower()) if t not in _STOP]


TAG_MATCH_MODES = ("any", "all", "any_strict", "all_strict", "exact")


def match_tag_group(item_tags: list[str], group: dict[str, Any]) -> bool:
    """Evaluate one tag group against one item's tags, mirroring the Hindsight server.

    Group forms: ``{"tags": [...], "match": mode}``, ``{"and": [...]}``, ``{"or": [...]}``,
    ``{"not": <group>}``. A top-level list of groups is AND-ed by the caller.

    Modes follow the server: ``any`` (OR) and ``all`` (AND) also admit an item with no tags
    at all; ``any_strict`` / ``all_strict`` do not; ``exact`` is set equality and excludes
    untagged items.
    """
    if "not" in group:
        return not match_tag_group(item_tags, group["not"])
    if "and" in group:
        return all(match_tag_group(item_tags, g) for g in group["and"])
    if "or" in group:
        return any(match_tag_group(item_tags, g) for g in group["or"])
    wanted = set(group.get("tags") or [])
    mode = group.get("match") or "any"
    if mode not in TAG_MATCH_MODES:
        raise ValueError(f"unknown tag match mode: {mode!r}")
    have = set(item_tags)
    if mode == "exact":
        return bool(have) and have == wanted
    if not have:
        return not mode.endswith("_strict")
    if mode.startswith("all"):
        return wanted <= have
    return bool(wanted & have)


def _tag_groups_for(tags: list[str] | None, tags_match: str) -> list[dict[str, Any]] | None:
    """Express a flat tag filter as a group list so both forms share one evaluator."""
    return [{"tags": list(tags), "match": tags_match}] if tags else None


class FakeMemory:
    """OFFLINE / TEST-ONLY. Keyword-overlap memory with the same interface as HindsightMemory.

    Exists so tests and the offline smoke run need no server or keys. It is not
    Hindsight and has none of its retrieval quality.
    """

    name = "fake-offline"

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def ensure_bank(self) -> None:
        self.calls.append(("ensure_bank", {}))

    def retain(self, content, *, context=None, timestamp=None, tags=None, document_id=None, metadata=None):
        self.calls.append(("retain", {"content": content, "tags": tags}))
        self._store(content, context, timestamp, tags, document_id, metadata)

    def _store(self, content, context, timestamp, tags, document_id, metadata):
        self.items.append(
            {
                "content": content,
                "context": context,
                "timestamp": timestamp,
                "tags": list(tags or []),
                "document_id": document_id,
                "metadata": dict(metadata or {}),
            }
        )

    def retain_many(self, items):
        self.calls.append(("retain_many", {"n": len(items)}))
        for it in items:
            self._store(
                it["content"], it.get("context"), it.get("timestamp"), it.get("tags"),
                it.get("document_id"), it.get("metadata"),
            )

    def recall(
        self,
        query,
        *,
        tags=None,
        max_tokens=2048,
        budget="mid",
        query_timestamp=None,
        tags_match="any",
        tag_groups=None,
    ):
        if tags and tag_groups:
            raise ValueError("pass either tags or tag_groups, not both: the server rejects that combination")
        self.calls.append(
            ("recall", {"query": query, "tags": tags, "tags_match": tags_match, "tag_groups": tag_groups})
        )
        q = set(_tokens(query))
        if not q:
            return []
        groups = tag_groups if tag_groups is not None else _tag_groups_for(tags, tags_match)
        n = max(len(self.items), 1)
        df: dict[str, int] = {}
        for it in self.items:
            for t in set(_tokens(it["content"])):
                df[t] = df.get(t, 0) + 1
        scored = []
        for it in self.items:
            if groups and not all(match_tag_group(it["tags"], g) for g in groups):
                continue
            toks = set(_tokens(it["content"]))
            score = sum(math.log(1 + n / df.get(t, 1)) for t in q & toks)
            if score > 0:
                scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        budget_chars = max_tokens * 4
        out: list[MemoryHit] = []
        used = 0
        for _, it in scored:
            if used + len(it["content"]) > budget_chars and out:
                break
            used += len(it["content"])
            out.append(
                MemoryHit(
                    text=it["content"],
                    type=it["metadata"].get("kind", "world"),
                    occurred_at=it["timestamp"],
                    tags=it["tags"],
                    context=it["context"],
                    document_id=it["document_id"],
                    metadata=it["metadata"],
                )
            )
            if len(out) >= 8:
                break
        return out

    def reflect(self, query, *, context=None, tags=None):
        self.calls.append(("reflect", {"query": query, "tags": tags}))
        hits = self.recall(query, tags=tags, max_tokens=1024)
        if not hits:
            return "No relevant memories to reflect on."
        return "[offline reflect stand-in] Related memories: " + " | ".join(h.text[:160] for h in hits[:3])


def days_ago(iso: str | None, now: datetime) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None and now.tzinfo is not None:
            dt = dt.replace(tzinfo=now.tzinfo)
        # Writes are stamped with server time, so a replayed "now" can sit behind a fresh
        # memory. Showing "-6 days ago" would be nonsense: call anything that recent "today".
        return max(0, (now - dt).days)
    except Exception:
        return None
