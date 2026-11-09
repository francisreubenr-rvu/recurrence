import pytest

from recurrence.agent import EXCLUDE_ADVICE, RecurrenceAgent
from recurrence.llm import OfflineLLM
from recurrence.memory import FakeMemory, HindsightMemory, days_ago
from recurrence.seed import load_data, seed
from datetime import datetime

NOW = datetime.fromisoformat("2026-11-09T19:47:00+05:30")


def test_seed_counts(seeded_memory):
    from recurrence.seed import all_items
    assert len(seeded_memory.items) == len(all_items())
    assert seeded_memory.calls[0][0] == "ensure_bank"


def test_recall_finds_matching_incident(seeded_memory):
    hits = seeded_memory.recall("Kafka consumer lag notif-worker deserialize partition")
    assert hits and any("INC-2031" in h.text for h in hits)


def test_recall_tag_filter(seeded_memory):
    hits = seeded_memory.recall("prefers step-by-step instructions", tags=["engineer:arjun-mehta"])
    assert hits and all("engineer:arjun-mehta" in h.tags for h in hits)


def test_recall_empty_query_and_no_match():
    m = FakeMemory()
    assert m.recall("the a an") == []
    m.retain("alpha beta", tags=["x"])
    assert m.recall("gamma") == []


def test_reflect_labelled_offline(seeded_memory):
    assert seeded_memory.reflect("ledger-svc migration lock").startswith("[offline reflect stand-in]")
    assert FakeMemory().reflect("anything") == "No relevant memories to reflect on."


def test_days_ago():
    now = datetime.fromisoformat("2026-11-09T19:47:00+05:30")
    assert days_ago("2026-10-15T19:55:00+05:30", now) == 24
    assert days_ago(None, now) is None and days_ago("garbage", now) is None


def test_recall_tags_match_all(seeded_memory):
    hits = seeded_memory.recall("Arjun Mehta incident", tags=["engineer:arjun-mehta", "kind:preference"], tags_match="all")
    assert hits and all({"engineer:arjun-mehta", "kind:preference"} <= set(h.tags) for h in hits)


def test_fake_memory_any_includes_untagged():
    m = FakeMemory()
    m.retain("untagged pool note", tags=[])
    m.retain("tagged pool note", tags=["kind:service"])
    plain = m.recall("pool note", tags=["kind:service"], tags_match="any")
    strict = m.recall("pool note", tags=["kind:service"], tags_match="any_strict")
    assert {h.text for h in plain} == {"untagged pool note", "tagged pool note"}
    assert {h.text for h in strict} == {"tagged pool note"}


def test_tag_groups_not_excludes_advice(seeded_memory):
    seeded_memory.retain(
        "Recurrence advised restarting payments-api pods for the HikariPool exhaustion",
        tags=["service:payments-api", "kind:advice"],
        metadata={"kind": "advice", "service": "payments-api"},
    )
    hits = seeded_memory.recall("HikariPool exhaustion payments-api", tag_groups=[EXCLUDE_ADVICE])
    assert hits
    assert not any("kind:advice" in h.tags for h in hits)
    assert any("kind:incident" in h.tags for h in hits), "real postmortems must survive the exclusion"


def test_tag_groups_not_keeps_untagged():
    m = FakeMemory()
    m.retain("payments-api pool exhausted runbook step")
    m.retain("payments-api pool advice", tags=["service:payments-api", "kind:advice"], metadata={"kind": "advice"})
    hits = m.recall("payments-api pool", tag_groups=[EXCLUDE_ADVICE])
    assert [h.text for h in hits] == ["payments-api pool exhausted runbook step"]


def test_never_both_tags_and_tag_groups(seeded_memory):
    seen: list[dict] = []

    class Spy(FakeMemory):
        def recall(self, *a, **k):
            seen.append(k)
            assert not (k.get("tags") and k.get("tag_groups")), "a recall call set both tags and tag_groups"
            return super().recall(*a, **k)

    spy = Spy()
    seed(spy)
    a = load_data()["demo_alerts"][0]
    assert RecurrenceAgent(spy, OfflineLLM()).answer(a["alert"], a["engineer"], a["service"], now=NOW)["answer"]
    assert seen, "the agent must have recalled something"

    for backend in (FakeMemory(), HindsightMemory("http://x", "b", client=object())):
        with pytest.raises(ValueError):
            backend.recall("q", tags=["kind:advice"], tag_groups=[EXCLUDE_ADVICE])
