<!-- DRAFT for Gopreeth Saharsh. Angle: before/after evaluation. Rewrite in your own voice before publishing (see content/README_FIRST.md). Fill every <RESULT_FROM_EVAL> with numbers from the LIVE run only (Hindsight + Groq), never from the offline mode. Remove this comment and every [SCREENSHOT: ...] marker before publishing. -->

# How I Measured Whether Hindsight Memory Actually Helped

"Our agent has memory" is easy to say and hard to prove. A demo where the agent says the right thing once is an anecdote. I wanted to know, with numbers I could defend, whether adding [Hindsight](https://github.com/vectorize-io/hindsight) to our on-call agent changed what it said. I also wanted to know how that change shows up over a sequence of pages, not just in a single answer.

This is how I set up the before/after evaluation for Recurrence, what it measures, what it can't, and what came out.

## The agent being tested

Recurrence is an SRE on-call agent for Tamarind Pay, a fictional payments company with synthetic but realistic incident history: twelve incidents over about seven weeks, each with an alert, logs, a root cause, a working fix and (often) a fix that didn't work. When a page fires, the agent recalls similar past incidents and the on-call engineer's preferences from a Hindsight bank, and a Groq-hosted model (`openai/gpt-oss-120b`, falling back to `qwen/qwen3-32b`) writes the answer.

The key property for testing is that **memory is a switch.** `agent.answer(..., memory_on=False)` skips both recalls and the retain, and gives the model no tools. Same model, same prompt template, same page. The only difference is memory.

## What "better" means here

It is tempting to have another LLM rate both answers on a 1–10 scale. I didn't, for two reasons: LLM judges are noisy on technical detail, and "sounds more helpful" is not what an engineer needs at 7:47 pm. What they need is: *does the agent recognise that this has happened before, and point to the right incident?*

That gives two binary metrics per page, and both can be checked against ground truth:

- **`recall_hit`**: did an expected incident ID appear in what Hindsight returned? This tests the memory layer alone.
- **`answer_cites`**: did an expected incident ID appear in the model's final answer? This tests whether the model *used* what was recalled.

Separating them matters. If recall finds the incident but the answer doesn't mention it, that's a prompt problem. If recall misses, it's a retain/recall problem. One score would hide which.

Each demo alert in `data/incidents.json` carries its ground truth:

```json
{
  "id": "DEMO-1",
  "engineer": "Arjun Mehta",
  "service": "payments-api",
  "alert": "HighErrorRate: payments-api 5xx ratio 19.2% (SLO 0.5%) for 5m\nERROR ... HikariPool-1 - Connection is not available ... (total=40, active=40, idle=0, waiting=201)\nLOG: process 51877 still waiting for AccessExclusiveLock on relation 16502 of database ledger",
  "expected_incident_ids": ["INC-2087", "INC-2041"]
}
```

## The harness

The whole eval is about 60 lines (`evals/before_after.py`). The core loop:

```python
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
```

Two choices I'd point out. Each alert carries its own `now`, so "25 days ago" comes out the same on every run instead of depending on when you run it. And the memory-off run goes *first* for each alert, because the memory-on run retains the agent's advice into the bank. If the order were reversed, the second run would be reading the first run's output.

Results go to `evals/results_<memory>_<llm>.json`, and the backend names are in the filename. That was on purpose: the repo also has an offline mode (a keyword-overlap fake memory and a template "LLM") so the tests run without keys. Its numbers are a plumbing check and nothing else. The filename makes it hard to quote the wrong file by accident.

## Results

Live run: Hindsight bank `recurrence-tamarind-sre`, Groq `<RESULT_FROM_EVAL: model actually used>`, five demo alerts, run on <RESULT_FROM_EVAL: date and time IST>.

| Metric | Memory OFF | Memory ON |
|---|---|---|
| Expected incident in recall (`recall_hit`) | <RESULT_FROM_EVAL> | <RESULT_FROM_EVAL> |
| Expected incident cited in answer (`answer_cites`) | <RESULT_FROM_EVAL> | <RESULT_FROM_EVAL> |

[SCREENSHOT: terminal output of `python -m evals.before_after --no-seed` with the summary JSON]

Memory-off recall is zero by design: nothing is recalled. Memory-off citation shows how often the model guesses a plausible incident ID with no memory at all. It should be near zero, and the system prompt says "Never invent incident IDs", but it's worth measuring rather than assuming.

## The learning curve: interaction 1 vs interaction 5

A static eval with a pre-seeded bank shows memory helps when the history is already there. It doesn't show the agent *learning.* For that, `scripts/learning_curve.py` starts from an **empty** bank and plays five interactions for one engineer, in date order:

1. **20 Oct:** a payments-api 5xx page with Hikari exhaustion. Nothing to recall. Afterwards, the real outcome (migration lock, `pg_terminate_backend`, rollback; restart and HPA scale *didn't* work) is retained.
2. **24 Oct:** the engineer states a preference: step by step, with a verify check after each step.
3. **28 Oct:** a PgBouncer saturation page from a BI query on the primary. Outcome retained.
4. **3 Nov:** a DNS latency page (`ndots:5`). Outcome retained, including "restarting CoreDNS didn't work".
5. **9 Nov:** the 5xx-plus-lock-wait page again.

**Interaction 1** (paste the live output): generic triage, because there is nothing to recall.

**Interaction 5** (paste the live output): it should name the incident from 20 days earlier, warn against the restart and the HPA scale-out, and give the steps in the engineer's preferred format.

[SCREENSHOT: interaction 1 and interaction 5 answers side by side from the learning-curve run]

In our live run, interaction 5 recalled <RESULT_FROM_EVAL> memories and <RESULT_FROM_EVAL> preference(s), and the answer <RESULT_FROM_EVAL: did / did not> name the earlier incident.

Everything the agent knows at step 5 came from steps 1–4. Nothing was pre-loaded. That's the claim I'm most comfortable defending.

## What this eval can't tell you

I want to be explicit about this, because eval write-ups often aren't.

**Five alerts is small.** It's enough to see whether the system works end to end. It's not enough for a confidence interval, and I wouldn't quote a percentage from it as if it would generalise.

**String matching on IDs is strict in one direction and loose in the other.** An answer that describes INC-2087 perfectly without the ID counts as a miss. An answer that mentions the ID in a confused way counts as a hit. Spot-check the answers by hand; don't trust only the booleans.

**It doesn't measure the dead-end warning or the preference formatting**, which are arguably the most valuable behaviours. Both need a human or a carefully scoped judge. The next metric I'd add is `avoids_dead_end`: did the answer recommend any fix listed as "did NOT work" for the matched incident? That one is checkable with string matching too.

**The data is synthetic.** It's modelled on real failure modes, but it was written by people who knew the answers. Real incident history is messier, and real recall will be harder.

## Lessons

1. Make memory a single switch in your agent so before/after is a one-argument change.
2. Measure retrieval and use separately; they fail for different reasons.
3. Pin "now" per test case if your agent reasons about time.
4. Run the no-memory condition first if the memory-on condition writes to memory.
5. Put the backend name in the results filename so offline numbers never get quoted.

[Hindsight's documentation](https://hindsight.vectorize.io/) covers the retain/recall/reflect APIs the harness uses, and Vectorize has a clear explainer on [what agent memory is and why it matters](https://vectorize.io/what-is-agent-memory). The eval code is in our repo: https://github.com/francisreubenr-rvu/recurrence.

<CODE_IN_LINE: one honest sentence tagging Code.in. If you did not use it, write a neutral mention rather than claiming you did.>
