"""Before/after eval: does the answer name the right past incident, with memory ON vs OFF?

    python -m evals.before_after --offline   # fake memory + template LLM (plumbing check only)
    python -m evals.before_after             # live: Hindsight + Groq from .env

Metrics per demo alert (data/incidents.json -> demo_alerts):
  recall_hit  - an expected incident ID appears in the recalled memories (memory ON only)
  answer_cites - an expected incident ID appears in the answer text
Writes evals/results_<memory>_<llm>.json. Only quote numbers from a LIVE run publicly.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from recurrence.agent import RecurrenceAgent
from recurrence.config import Settings, build_llm, build_memory
from recurrence.seed import load_data, seed


def run(agent: RecurrenceAgent, alerts: list[dict]) -> dict:
    rows = []
    for a in alerts:
        now = datetime.fromisoformat(a["now"])
        row = {"id": a["id"], "expected": a["expected_incident_ids"]}
        for mode in (False, True):
            out = agent.answer(a["alert"], a["engineer"], a["service"], memory_on=mode, now=now)
            recalled = " ".join(m["text"] + " " + str(m.get("document_id")) for m in out["memories"])
            key = "on" if mode else "off"
            row[f"answer_cites_{key}"] = any(i in out["answer"] for i in a["expected_incident_ids"])
            row[f"recall_hit_{key}"] = any(i in recalled for i in a["expected_incident_ids"])
        rows.append(row)
    n = len(rows)
    summary = {
        k: sum(r[k] for r in rows) / n
        for k in ("recall_hit_off", "recall_hit_on", "answer_cites_off", "answer_cites_on")
    }
    return {"n": n, "summary": summary, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-seed", action="store_true", help="bank already seeded")
    args = ap.parse_args()
    s = Settings.from_env(offline=args.offline)
    agent = RecurrenceAgent(build_memory(s), build_llm(s))
    if not args.no_seed:
        seed(agent.memory)
    res = run(agent, load_data()["demo_alerts"])
    res["backend"] = {"memory": agent.memory.name, "llm": agent.llm.name}
    res["ran_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    out = Path(__file__).parent / f"results_{agent.memory.name}_{agent.llm.name}.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps({"backend": res["backend"], "n": res["n"], "summary": res["summary"]}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
