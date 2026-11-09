"""Check that HindsightMemory calls the real hindsight-client 1.2.0 API with valid signatures.

create_autospec makes the mock reject any keyword the real method does not accept.
"""
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from hindsight_client import Hindsight

from recurrence.memory import HindsightMemory, MemoryHit
from recurrence.seed import all_items


@pytest.fixture
def spec_client():
    return create_autospec(Hindsight, instance=True)


def test_ensure_bank_signature(spec_client):
    mem = HindsightMemory("http://x", "bank-1", client=spec_client)
    mem.ensure_bank()
    spec_client.create_bank.assert_called_once()
    kw = spec_client.create_bank.call_args.kwargs
    assert kw["bank_id"] == "bank-1"
    assert set(kw["disposition"]) == {"skepticism", "literalism", "empathy"}
    assert all(1 <= v <= 5 for v in kw["disposition"].values())


def test_ensure_bank_swallows_existing_bank(spec_client):
    spec_client.create_bank.side_effect = RuntimeError("409 bank exists")
    HindsightMemory("http://x", "b", client=spec_client).ensure_bank()  # must not raise


def test_retain_signature(spec_client):
    mem = HindsightMemory("http://x", "b", client=spec_client)
    mem.retain("hello", context="c", timestamp="2026-11-09T19:47:00+05:30", tags=["t"], document_id="d", metadata={"k": "v"})
    kw = spec_client.retain.call_args.kwargs
    assert kw["bank_id"] == "b" and kw["content"] == "hello" and kw["tags"] == ["t"]


def test_retain_batch_signature_and_items_are_valid(spec_client):
    mem = HindsightMemory("http://x", "b", client=spec_client)
    items = all_items()
    mem.retain_many(items)
    kw = spec_client.retain_batch.call_args.kwargs
    assert kw["bank_id"] == "b" and len(kw["items"]) == len(items)
    allowed = {"content", "timestamp", "context", "metadata", "document_id", "entities", "resolve_entities",
               "tags", "observation_scopes", "strategy", "update_mode"}
    for it in items:
        assert set(it) <= allowed
        # MemoryItem.metadata is Dict[str, StrictStr]
        assert all(isinstance(v, str) for v in it.get("metadata", {}).values())


def test_retain_batch_items_build_real_request_models():
    """Build the SDK's own MemoryItem models from our items, as retain_batch does, to catch type errors."""
    from hindsight_client_api.models.content import Content
    from hindsight_client_api.models.memory_item import MemoryItem
    from hindsight_client_api.models.timestamp import Timestamp

    for it in all_items():
        MemoryItem(
            content=Content(actual_instance=it["content"]),
            timestamp=Timestamp(actual_instance=it["timestamp"]) if it.get("timestamp") else None,
            context=it.get("context"),
            metadata=it.get("metadata"),
            document_id=it.get("document_id"),
            tags=it.get("tags"),
        )


def test_recall_signature_and_normalisation(spec_client):
    spec_client.recall.return_value = SimpleNamespace(
        results=[
            SimpleNamespace(text="INC-2087 lock", type="experience", occurred_start="2026-10-15T19:55:00+05:30",
                            mentioned_at=None, tags=["service:payments-api"], context="pm", document_id="INC-2087",
                            metadata={"incident_id": "INC-2087"}),
            SimpleNamespace(text="fact", type="world", occurred_start=None, mentioned_at=None, tags=None,
                            context=None, document_id=None, metadata=None),
        ]
    )
    mem = HindsightMemory("http://x", "b", client=spec_client)
    hits = mem.recall("q", tags=["service:payments-api"], max_tokens=500, query_timestamp="2026-11-09T19:47:00+05:30")
    mem.recall("prefs", tags=["engineer:arjun-mehta", "kind:preference"], tags_match="all")
    assert spec_client.recall.call_args.kwargs["tags_match"] == "all"
    kw = spec_client.recall.call_args_list[0].kwargs
    assert kw["tags_match"] == "any" and kw["query_timestamp"].startswith("2026-11-09")
    assert isinstance(hits[0], MemoryHit) and hits[0].document_id == "INC-2087"
    assert hits[1].tags == [] and hits[1].metadata == {} and hits[1].occurred_at is None


def test_recall_forwards_tag_groups(spec_client):
    spec_client.recall.return_value = SimpleNamespace(results=[])
    groups = [{"not": {"tags": ["kind:advice"], "match": "any_strict"}}]
    HindsightMemory("http://x", "b", client=spec_client).recall("q", tag_groups=groups, max_tokens=2500)
    kw = spec_client.recall.call_args.kwargs
    assert kw["tag_groups"] == groups
    assert kw["tags"] is None and kw["tags_match"] == "any"


def test_tag_groups_rejected_together_with_tags(spec_client):
    with pytest.raises(ValueError):
        HindsightMemory("http://x", "b", client=spec_client).recall(
            "q", tags=["kind:advice"], tag_groups=[{"tags": ["kind:advice"], "match": "any"}]
        )
    spec_client.recall.assert_not_called()


def test_reflect_signature(spec_client):
    spec_client.reflect.return_value = SimpleNamespace(text="pattern: ledger deploys")
    out = HindsightMemory("http://x", "b", client=spec_client).reflect("why?", tags=["service:ledger-svc"])
    assert out == "pattern: ledger deploys"
    assert spec_client.reflect.call_args.kwargs["budget"] == "low"
