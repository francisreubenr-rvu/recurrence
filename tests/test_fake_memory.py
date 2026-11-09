from recurrence.memory import FakeMemory, days_ago
from datetime import datetime


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
