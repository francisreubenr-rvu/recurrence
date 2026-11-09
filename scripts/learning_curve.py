"""Interaction 1 vs interaction 5, from an EMPTY memory bank.

Plays five pages for one engineer in order. After each page the real outcome is
retained (as an engineer would via the UI's "Close the loop" form). Page 1 has
nothing to recall; by page 5 the agent recalls the earlier outages, the failed
fixes and the engineer's stated preference.

    python -m scripts.learning_curve --offline
    python -m scripts.learning_curve            # live: uses bank <HINDSIGHT_BANK_ID>-curve
"""
from __future__ import annotations

import argparse
from datetime import datetime

from recurrence.agent import RecurrenceAgent
from recurrence.config import Settings, build_llm, build_memory

ENG = "Arjun Mehta"
SVC = "payments-api"

STEPS = [
    ("2026-10-20T19:50:00+05:30",
     "HighErrorRate: payments-api 5xx 18% for 5m\nHikariPool-1 - Connection is not available (total=40, active=40, waiting=190)",
     dict(summary="502s during evening peak", root_cause="ledger-svc migration held AccessExclusiveLock on ledger.entries",
          fix="pg_terminate_backend on the migration PID, roll back ledger-svc", did_not_work="restarting payments-api pods; scaling HPA")),
    ("2026-10-24T10:05:00+05:30", None, None),  # preference only
    ("2026-10-28T20:15:00+05:30",
     "HighErrorRate: payments-api 5xx 4% for 5m\npgbouncer: cl_waiting=96 sv_active=50/50",
     dict(summary="PgBouncer saturation", root_cause="BI query hit primary instead of replica",
          fix="kill query, point Metabase at replica, statement_timeout=30s for bi role", did_not_work="")),
    ("2026-11-03T09:30:00+05:30",
     "HighLatency: payments-api p99 2.4s\ncoredns: i/o timeout ledger-svc.payments.svc.cluster.local.payments.svc.cluster.local",
     dict(summary="DNS latency", root_cause="ndots:5 search-domain lookups + CoreDNS throttling",
          fix="ndots:2 and FQDN for ledger-svc", did_not_work="restarting CoreDNS")),
    ("2026-11-09T19:47:00+05:30",
     "HighErrorRate: payments-api 5xx 19.2% for 5m\nHikariPool-1 - Connection is not available (total=40, active=40, waiting=201)\nLOG: still waiting for AccessExclusiveLock on relation 16502 of database ledger",
     None),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--reuse-bank", action="store_true",
                    help="append to the existing -curve bank instead of starting from an empty timestamped one")
    args = ap.parse_args()
    s = Settings.from_env(offline=args.offline)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    s.bank_id = f"{s.bank_id}-curve" + ("" if args.reuse_bank else f"-{stamp}")
    print(f"bank: {s.bank_id}")
    agent = RecurrenceAgent(build_memory(s), build_llm(s))
    agent.memory.ensure_bank()
    for i, (when, alert, outcome) in enumerate(STEPS, 1):
        now = datetime.fromisoformat(when)
        print(f"\n===== Interaction {i} · {when} =====")
        if alert is None:
            agent.remember_preference(ENG, "Arjun prefers step-by-step instructions with a 'how to verify' check after each step.", now=now)
            print("Engineer taught a preference -> retained.")
            continue
        out = agent.answer(alert, ENG, SVC, memory_on=True, now=now)
        print(f"recalled {len(out['memories'])} memories, {len(out['preferences'])} preferences")
        for m in out["memories"][:3]:
            print(f"  - ({m['days_ago']} days ago) {m['text'][:110]}")
        print("ANSWER:\n" + out["answer"])
        if outcome:
            agent.resolve(SVC, ENG, now=now, **outcome)
            print("Outcome retained.")


if __name__ == "__main__":
    main()
