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


def test_call_log_is_bounded():
    from recurrence.memory import FakeMemory

    mem = FakeMemory()
    for i in range(600):
        mem.retain(f"memory {i}")
    assert len(mem.calls) <= 500
    assert len(mem.items) == 600


def test_concurrent_retain_and_recall_are_safe():
    import threading

    from recurrence.memory import FakeMemory

    mem = FakeMemory()
    errors = []

    def writer(n):
        try:
            for i in range(100):
                mem.retain(f"payments-api HikariPool timeout {n}-{i}", tags=["service:payments-api"])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def reader():
        try:
            for _ in range(100):
                mem.recall("HikariPool timeout")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    threads += [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(mem.items) == 400
