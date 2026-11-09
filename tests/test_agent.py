from datetime import datetime

from recurrence.agent import RecurrenceAgent
from recurrence.memory import FakeMemory
from recurrence.seed import load_data

NOW = datetime.fromisoformat("2026-11-09T19:47:00+05:30")


def demo1():
    return load_data()["demo_alerts"][0]


def test_memory_off_is_generic_and_writes_nothing(seeded_memory, offline_llm):
    a = demo1()
    agent = RecurrenceAgent(seeded_memory, offline_llm)
    before = len(seeded_memory.items)
    out = agent.answer(a["alert"], a["engineer"], a["service"], memory_on=False, now=NOW)
    assert out["memories"] == [] and out["preferences"] == []
    assert "no memory" in out["answer"].lower()
    assert not any(i in out["answer"] for i in a["expected_incident_ids"])
    assert len(seeded_memory.items) == before


def test_memory_on_recalls_past_incident_and_retains_advice(seeded_memory, offline_llm):
    a = demo1()
    agent = RecurrenceAgent(seeded_memory, offline_llm)
    before = len(seeded_memory.items)
    out = agent.answer(a["alert"], a["engineer"], a["service"], memory_on=True, now=NOW)
    recalled = " ".join(m["text"] for m in out["memories"])
    assert any(i in recalled for i in a["expected_incident_ids"])
    assert any(i in out["answer"] for i in a["expected_incident_ids"])
    assert out["preferences"], "engineer preference should be recalled"
    assert all("kind:preference" in p["tags"] for p in out["preferences"])
    dated = [m for m in out["memories"] if m["occurred_at"]]  # service-catalog facts are timeless
    assert dated and all(m["days_ago"] >= 0 for m in dated)
    assert len(seeded_memory.items) == before + 1
    assert seeded_memory.items[-1]["metadata"]["kind"] == "advice"


def test_memory_down_does_not_block_page(offline_llm):
    class Broken(FakeMemory):
        def recall(self, *a, **k):
            raise ConnectionError("hindsight down")

        def retain(self, *a, **k):
            raise ConnectionError("hindsight down")

    out = RecurrenceAgent(Broken(), offline_llm).answer("5xx spike", "Arjun Mehta", "payments-api", now=NOW)
    assert out["answer"] and len(out["memory_errors"]) == 3


def test_llm_down_still_returns(seeded_memory):
    class DeadLLM:
        name = "dead"

        def run(self, *a, **k):
            raise RuntimeError("groq down")

    out = RecurrenceAgent(seeded_memory, DeadLLM()).answer("HikariPool exhausted", "Arjun Mehta", "payments-api", now=NOW)
    assert "unreachable" in out["answer"] and out["tool_trace"][0]["event"] == "llm_unavailable"


def test_resolve_writes_incident_and_dead_end(offline_llm):
    mem = FakeMemory()
    agent = RecurrenceAgent(mem, offline_llm)
    n = agent.resolve("payments-api", "Arjun Mehta", "502s", "lock", "kill pid", did_not_work="restart pods", now=NOW)
    assert n == 2 and {i["metadata"]["kind"] for i in mem.items} == {"incident", "dead-end"}
    assert agent.resolve("payments-api", "Arjun Mehta", "x", "y", "z", now=NOW) == 1


def test_preference_learned_then_used(offline_llm):
    mem = FakeMemory()
    agent = RecurrenceAgent(mem, offline_llm)
    agent.resolve("payments-api", "Arjun Mehta", "pool exhausted HikariPool", "lock", "kill pid", "restart pods", "INC-9001", now=NOW)
    agent.remember_preference("Arjun Mehta", "prefers step-by-step instructions with a verify check", now=NOW)
    out = agent.answer("HikariPool connection not available", "Arjun Mehta", "payments-api", now=NOW)
    assert len(out["preferences"]) == 1 and "step by step" in out["answer"].lower()
    assert "Do NOT repeat" in out["answer"]


def test_execute_tools(seeded_memory, offline_llm):
    agent = RecurrenceAgent(seeded_memory, offline_llm)
    assert "INC-2031" in agent._execute("recall_memory", {"query": "kafka lag notif-worker", "service": "notif-worker"})
    assert "answer" in agent._execute("reflect_on_history", {"question": "kafka lag"})


def test_offline_template_does_not_echo_its_own_advice(offline_llm):
    """Regression: retained advice quoting a dead end must not be re-quoted as 'Do NOT repeat: Do NOT repeat:'."""
    mem = FakeMemory()
    agent = RecurrenceAgent(mem, offline_llm)
    agent.resolve("payments-api", "Arjun Mehta", "HikariPool exhausted", "lock", "kill pid", "restart pods", "INC-9001", now=NOW)
    for _ in range(3):
        out = agent.answer("HikariPool connection not available", "Arjun Mehta", "payments-api", now=NOW)
    assert "Do NOT repeat: Do NOT repeat" not in out["answer"]
    assert "INC-9001" in out["answer"]
