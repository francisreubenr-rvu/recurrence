import re
from datetime import datetime

from recurrence.agent import RecurrenceAgent
from recurrence.memory import FakeMemory
from recurrence.seed import load_data

NOW = datetime.fromisoformat("2026-11-09T19:47:00+05:30")
ADVICE_HEADING = "PRIOR ADVICE (unconfirmed, may have been wrong)"


def demo1():
    return load_data()["demo_alerts"][0]


class CaptureLLM:
    """Records the system prompt so tests can assert what the model was actually shown."""

    name = "capture"
    answer = "Restart nothing yet: check the ledger-svc lock first."

    def __init__(self):
        self.system = ""

    def run(self, messages, tools, execute, max_rounds: int = 4):
        self.system = messages[0]["content"]
        return self.answer, []


def sections(system: str) -> dict[str, str]:
    """Split the prompt into its labelled blocks, so a test can prove where a memory landed."""
    out: dict[str, str] = {}
    for marker, key in (("ENGINEER PREFERENCES", "prefs"), (ADVICE_HEADING, "advice"), ("PAST INCIDENT MEMORIES", "incidents")):
        if marker not in system:
            continue
        tail = system.split(marker, 1)[1]
        for later in ("ENGINEER PREFERENCES", ADVICE_HEADING, "PAST INCIDENT MEMORIES"):
            if later != marker and later in tail:
                tail = tail.split(later, 1)[0]
        out[key] = tail
    return out


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
    # three recalls (incidents, preferences, prior advice) plus the advice write
    assert out["answer"] and len(out["memory_errors"]) >= 3


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


def test_advice_still_retained(seeded_memory, offline_llm):
    a = demo1()
    agent = RecurrenceAgent(seeded_memory, offline_llm)
    before = len(seeded_memory.items)
    out = agent.answer(a["alert"], a["engineer"], a["service"], memory_on=True, now=NOW)
    assert len(seeded_memory.items) == before + 1
    stored = seeded_memory.items[-1]
    assert stored["metadata"]["kind"] == "advice" and "kind:advice" in stored["tags"]
    assert out["prior_advice"] == []  # nothing had been advised before this first page
    assert not any("kind:advice" in m["tags"] for m in out["memories"])


def test_advice_still_reaches_prompt(seeded_memory):
    llm = CaptureLLM()
    agent = RecurrenceAgent(seeded_memory, llm)
    a = demo1()
    agent.answer(a["alert"], a["engineer"], a["service"], now=NOW)  # first page retains advice
    out = agent.answer(a["alert"], a["engineer"], a["service"], now=NOW)
    blocks = sections(llm.system)
    assert ADVICE_HEADING in llm.system and "PAST INCIDENT MEMORIES" in llm.system
    assert llm.answer in blocks["advice"], "prior advice must reach the model in its own section"
    assert llm.answer not in blocks["incidents"], "advice must never be merged into incident memories"
    assert len(out["prior_advice"]) == 1
    assert out["prior_advice"][0]["metadata"]["kind"] == "advice"


def test_advice_capped_and_deduped():
    mem = FakeMemory()
    for i in range(5):
        mem.retain(
            f"payments-api HikariPool pool advice number {i}",
            tags=["service:payments-api", "kind:advice"],
            metadata={"kind": "advice", "service": "payments-api"},
        )
    mem.retain(  # byte-identical repeat of the first, as a re-quoted page would produce
        "payments-api HikariPool pool advice number 0",
        tags=["service:payments-api", "kind:advice"],
        metadata={"kind": "advice", "service": "payments-api"},
    )
    llm = CaptureLLM()
    out = RecurrenceAgent(mem, llm).answer("HikariPool exhausted", "Arjun Mehta", "payments-api", now=NOW)
    rows = [l for l in sections(llm.system)["advice"].splitlines() if l.startswith("- [ADVICE")]
    assert 0 < len(rows) <= 3
    assert len(set(rows)) == len(rows), "no duplicate advice row"
    assert len(out["prior_advice"]) == len(rows)


def test_recall_failure_still_answers(offline_llm):
    class BrokenRecall(FakeMemory):
        def recall(self, *a, **k):
            raise ConnectionError("hindsight down")

    out = RecurrenceAgent(BrokenRecall(), offline_llm).answer("5xx spike", "Arjun Mehta", "payments-api", now=NOW)
    assert out["answer"]
    assert out["memories"] == [] and out["preferences"] == [] and out["prior_advice"] == []
    assert any(e.startswith("recall(incidents)") for e in out["memory_errors"])


def test_prompt_labels_kind_and_incident_id(seeded_memory):
    llm = CaptureLLM()
    agent = RecurrenceAgent(seeded_memory, llm)
    a = demo1()
    agent.answer(a["alert"], a["engineer"], a["service"], now=NOW)
    blocks = sections(llm.system)
    assert re.search(r"- \[INCIDENT INC-2087, 24 days ago\]", blocks["incidents"])
    assert "- [SERVICE service:payments-api]" in blocks["incidents"]
    assert re.search(r"- \[PREFERENCE, \d+ days ago\]", blocks["prefs"])
    # a page that asks about a failed fix is the one that recalls dead ends
    agent.answer("payments-api 5xx restarting payments-api pods did not work", "Arjun Mehta", "payments-api", now=NOW)
    dead_ends = sections(llm.system)["incidents"]
    assert re.search(r"- \[DEAD END INC-2041, \d+ days ago\]", dead_ends)


def test_llm_down_does_not_retain(seeded_memory):
    class DeadLLM:
        name = "dead"

        def run(self, *a, **k):
            raise RuntimeError("groq down")

    before = len(seeded_memory.items)
    out = RecurrenceAgent(seeded_memory, DeadLLM()).answer("HikariPool exhausted", "Arjun Mehta", "payments-api", now=NOW)
    assert out["tool_trace"][0]["event"] == "llm_unavailable"
    assert len(seeded_memory.items) == before, "an unavailable LLM must not be remembered as advice"


def test_retained_timestamp_uses_server_time(seeded_memory, offline_llm):
    replay = datetime.fromisoformat("1999-01-01T00:00:00+05:30")
    agent = RecurrenceAgent(seeded_memory, offline_llm)
    agent.answer("HikariPool exhausted", "Arjun Mehta", "payments-api", now=replay)
    agent.resolve("payments-api", "Arjun Mehta", "s", "rc", "fix", now=replay)
    now = datetime.now().astimezone()
    for item in seeded_memory.items:
        if item["timestamp"]:  # the seeded history is dated 2026; only the fresh writes matter here
            assert not item["timestamp"].startswith("1999")
    fresh = [i for i in seeded_memory.items if i["metadata"].get("kind") in ("advice", "incident")]
    assert fresh and all(datetime.fromisoformat(i["timestamp"]).year == now.year for i in fresh)


def test_resolve_ids_unique_same_minute(monkeypatch, offline_llm):
    ticks = iter(["aa", "bb"])
    monkeypatch.setattr("recurrence.agent.secrets.token_hex", lambda n: next(ticks))
    mem = FakeMemory()
    agent = RecurrenceAgent(mem, offline_llm)
    first = agent.resolve("payments-api", "Arjun Mehta", "s", "rc", "fix", now=NOW)
    second = agent.resolve("payments-api", "Arjun Mehta", "s", "rc", "fix", now=NOW)
    ids = [i["document_id"] for i in mem.items]
    assert re.fullmatch(r"INC-LIVE-\d{10}-aa", ids[0]), "incident id must carry seconds plus random hex"
    assert len(set(ids)) == len(ids) == 2, "two resolves in the same minute must not collide"
    assert (first, second) == (1, 1)  # no did_not_work, so one incident memory each


def test_offline_template_does_not_echo_its_own_advice(offline_llm):
    """Regression: retained advice quoting a dead end must not be re-quoted as 'Do NOT repeat: Do NOT repeat:'."""
    mem = FakeMemory()
    agent = RecurrenceAgent(mem, offline_llm)
    agent.resolve("payments-api", "Arjun Mehta", "HikariPool exhausted", "lock", "kill pid", "restart pods", "INC-9001", now=NOW)
    for _ in range(3):
        out = agent.answer("HikariPool connection not available", "Arjun Mehta", "payments-api", now=NOW)
    assert "Do NOT repeat: Do NOT repeat" not in out["answer"]
    assert "INC-9001" in out["answer"]
