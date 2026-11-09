<!-- DRAFT for Francis Reuben R. Angle: architecture. Rewrite in your own voice before publishing (see content/README_FIRST.md). Remove this comment, every [SCREENSHOT: ...] marker and every <RESULT_FROM_EVAL> before publishing. -->

# I Gave Our On-Call Agent a Memory With Hindsight

At 7:47 pm a page fires: payments-api is returning 5xx on 19% of requests, the Hikari connection pool is at 40/40 with 201 threads waiting, and Postgres says a process is "still waiting for AccessExclusiveLock on relation 16502". Any LLM you paste that into will tell you to restart the pods and scale out.

At our (fictional) payments company, Tamarind Pay, that exact advice made the same outage worse twice: 25 days ago and 46 days ago. A stateless model can't know that. So I built Recurrence, an on-call agent whose main job is to remember, on top of [Hindsight's open-source agent memory](https://github.com/vectorize-io/hindsight).

This post covers how the system hangs together, and the one design rule that shaped every layer: **memory should make the answer better, but must never be the reason there is no answer.**

[SCREENSHOT: the Recurrence console with the 7:47 pm page on the left and "Recalled from memory" on the right, showing "25 days ago" and "46 days ago"]

## What it does

Recurrence takes a page (the alert text plus a few log lines), the service name and the on-call engineer. It answers in under 200 words, leading with the most likely fix. With memory on, it does four things a generic assistant can't:

1. It says which past incident this repeats, and how many days ago it happened.
2. It lists the fixes that *didn't* work last time, so you skip them.
3. It formats the answer the way *this* engineer has asked for it.
4. After the page, it retains what it advised. When the incident is closed, it retains the confirmed root cause, the fix and the dead ends.

The data is synthetic, but modelled on failure modes most of us have lived through: a schema migration taking a lock during peak traffic, a poison message stalling a Kafka partition, `ndots:5` turning one DNS lookup into five, a CDN returning 526 after a cert rate limit, and more. Twelve incidents across six services, plus engineer preferences and service facts.

## How it hangs together

There are four pieces:

```
page ──► FastAPI (/api/ask) ──► RecurrenceAgent
                                   │  recall (incidents)      ┐
                                   │  recall (engineer prefs) ├─► Hindsight bank
                                   │  retain (advice given)   ┘   "recurrence-tamarind-sre"
                                   └► Groq LLM (gpt-oss-120b → qwen3-32b fallback)
                                        tools: recall_memory, reflect_on_history
```

- **Hindsight** holds everything the team knows, in one memory bank. Tags scope it: `service:payments-api`, `engineer:arjun-mehta`, `kind:incident`, `kind:dead-end`, `kind:preference`.
- **Groq** runs the model through its OpenAI-compatible endpoint. I picked it for speed; on-call answers need to come back in seconds.
- **The agent** recalls before the model call, so the model starts with the right context. It also gives the model two tools, `recall_memory` and `reflect_on_history`, for follow-up questions.
- **The UI** is one page: page in, answer out, recalled memories (with their age) on the side, and a "Close the loop" form that retains the real outcome.

[SCREENSHOT: architecture diagram with Hindsight sitting between the agent and the incident history]

## Keeping the memory layer small

I did not want Hindsight calls spread through the agent. Everything goes through a small interface with two implementations: `HindsightMemory` (the real one) and a deliberately dumb keyword store, used only for offline tests. Here is the real recall, from `recurrence/memory.py`:

```python
def recall(self, query, *, tags=None, max_tokens=2048, budget="mid"):
    resp = self.client.recall(
        bank_id=self.bank_id,
        query=query,
        max_tokens=max_tokens,
        budget=budget,
        tags=tags,
        tags_match="any",
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
```

Two details matter here. First, `max_tokens` is a budget, not a result count. Incident recall gets 2,500 tokens and preference recall gets 600, so the model's context stays predictable. Second, I keep `occurred_start` from each result. Every incident is retained with the timestamp it actually happened, so the agent can say "this is the same thing as 25 days ago" instead of "this resembles a past incident". In practice, that sentence is what builds an engineer's trust. The [Hindsight docs](https://hindsight.vectorize.io/) explain how recall combines semantic, keyword, graph and temporal retrieval. I didn't have to build any of that.

## Memory is optional, the answer is not

This was the most important decision. An on-call tool that crashes because its memory server is slow is worse than no tool. So every memory call in the answer path is wrapped, and any failure becomes a visible note instead of an exception. From `recurrence/agent.py`:

```python
if memory_on:
    try:
        incident_hits = self.memory.recall(f"{service}: {alert}", max_tokens=2500)
    except Exception as exc:  # memory down must not block the page
        memory_errors.append(f"recall(incidents) failed: {exc}")
```

The same idea applies to the model. Open models sometimes produce malformed tool calls; Groq then returns HTTP 400 with `tool_use_failed`. The LLM layer handles that in steps: retry transient errors, switch to the fallback model, and finally answer *without tools*. That last step still works, because the important memories were already recalled into the prompt before the first call. If the model is unreachable altogether, the UI still shows the recalled incidents, which are often enough for an engineer to act on.

Tool arguments get the same treatment. `safe_execute` never raises. A bad JSON argument or a failed recall goes back to the model as an error message ("Answer from the memories already in context"), so the conversation can recover instead of dying.

## Before and after

Same page, same model, with the memory toggle off and then on.

**Memory off** (abridged; paste your own live output here):

> 1. Check recent deploys and roll back if one lines up with the alert. 2. Check dashboards for error rate, latency, saturation. 3. Restart unhealthy pods if errors persist. 4. Scale out if CPU or connections are high. 5. Escalate to the service owner.

That isn't wrong in general. Here, steps 3 and 4 are exactly what made INC-2087 worse: more pods means more connections against PgBouncer's `max_client_conn=800`.

**Memory on** (abridged; paste your own live output here):

> This repeats INC-2087 (25 days ago) and INC-2041 (46 days ago): a ledger-svc migration holding a lock on `ledger.entries`. Step 1: find the blocking PID … `pg_terminate_backend` … Step 2: roll back ledger-svc … Do NOT restart payments-api pods or scale the HPA; both made it worse last time. Page Priya now.

[SCREENSHOT: memory OFF and memory ON answers side by side for the same page]

On our five demo alerts, the expected past incident was named in <RESULT_FROM_EVAL> of answers with memory on and <RESULT_FROM_EVAL> with memory off. (Gopreeth's post goes into how we measured that.)

## What I would do differently

**The fake memory was worth it, but it is a trap if you forget what it is.** I wrote `FakeMemory` so tests and offline runs need no server or keys. It is a keyword overlap, with none of Hindsight's fact extraction, entity graph or temporal ranking. I labelled it "OFFLINE / TEST-ONLY" in its docstring, in its `name`, and in every answer it produces. Even so, it is tempting to quote numbers from it. Don't. Only numbers from the live Hindsight bank are worth anything.

**Retaining the agent's own advice needs care.** After every page, Recurrence retains what it advised, tagged `kind:advice` and given the context "not yet confirmed as the fix". That stops it suggesting the same thing twice in one night. The risk is that unconfirmed advice could later be recalled as if it were a fix. The context string and tag are the guard, and the system prompt tells the model to prefer resolved incidents. I'd like a firmer separation here, so I'm calling it an open problem.

**Limitation: it is only as good as what gets retained.** If nobody fills in the "Close the loop" form, the next page learns nothing from this one. In a real deployment I'd pull postmortems straight from the incident tracker instead of relying on someone to type them in.

## Takeaways

1. Put memory behind a small interface from the start; you'll want an offline stand-in for tests.
2. Recall *before* the model call, then give the model recall as a tool too. Don't rely on tool calling alone.
3. Retain timestamps with every memory. "How long ago" turns out to be one of the most useful things the agent says.
4. Treat every memory and model call as something that can fail, and degrade to "here is what I remember" rather than an error.
5. Store what didn't work as its own memory. Aryan's post covers why.

If you are building agents that should get better with use, read Vectorize's piece on [what agent memory actually is](https://vectorize.io/what-is-agent-memory) and try [Hindsight](https://github.com/vectorize-io/hindsight). The code for Recurrence is at <REPO_URL>.

<CODE_IN_LINE: one honest sentence tagging Code.in, e.g. what you used it for. If you did not use it, write a neutral mention rather than claiming you did.>
