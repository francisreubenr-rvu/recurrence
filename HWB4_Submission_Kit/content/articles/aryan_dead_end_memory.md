<!-- DRAFT for Aryan Dubey. Angle: memory design and dead-end memories. Rewrite in your own voice before publishing (see content/README_FIRST.md). Remove this comment, every [SCREENSHOT: ...] marker and every <RESULT_FROM_EVAL> before publishing. -->

# Teaching an Agent What Not To Do, With Hindsight

Most postmortems have a section nobody reads twice: "What we tried that didn't work." It is the most useful paragraph in the document, and the one most often forgotten.

When I designed the memory for Recurrence, our on-call agent, I made one decision that shaped everything else: **failed fixes are first-class memories.** They aren't a footnote inside the incident write-up. They are separate items in the [Hindsight memory bank](https://github.com/vectorize-io/hindsight), with their own tag, so a page at 7:47 pm can bring up "do NOT restart the pods" even when the rest of the old incident isn't the best match.

This post covers how the memory is modelled, and why.

## The setup

Recurrence is an SRE agent for Tamarind Pay, a fictional payments company. Its synthetic history has twelve incidents across six services (payments-api, ledger-svc, checkout-web, notif-worker, auth-gateway, search-indexer), five engineer preferences, and a service catalogue. When a page comes in, the agent recalls related memories from Hindsight, and a Groq-hosted model answers with them in context.

The incident at the centre of our demo happened twice before it happens on screen:

- **INC-2041 (46 days before the demo page):** a ledger-svc migration took an `ACCESS EXCLUSIVE` lock on `ledger.entries` during evening UPI peak. payments-api queries queued behind it and exhausted the Hikari pool. Restarting pods bought 8 minutes. Scaling the HPA from 8 to 16 pods made it *worse*, because more pods meant more connections against PgBouncer.
- **INC-2087 (25 days before):** the same pattern, from a different migration (an index built without `CONCURRENTLY`). A newer on-call engineer restarted pods, then scaled the HPA, before paging the lead. That cost about 20 minutes.

The second incident is the whole point. The fix was known. What wasn't remembered was **what not to do.**

## One bank, three kinds of memory

Everything lives in one bank. I thought about one bank per service, but incidents cross services all the time (here, ledger-svc breaks payments-api), and splitting the banks would hide exactly the links we need. Tags do the scoping instead:

| Tag | Example | Used for |
|---|---|---|
| `service:` | `service:payments-api` | Scoping the `recall_memory` tool when the model asks about one service |
| `engineer:` | `engineer:arjun-mehta` | Recalling only this person's preferences |
| `kind:` | `incident`, `dead-end`, `preference`, `service`, `advice` | Telling the model what kind of memory it is reading |

The bank is created with a mission and a disposition, so Hindsight knows what it is for. From `recurrence/memory.py`:

```python
BANK_MISSION = (
    "I am the on-call memory for Tamarind Pay's SRE team. I remember every past "
    "incident: the alert, the logs, the root cause, the fix that worked, and the "
    "fixes that did NOT work. I also remember how each engineer likes to receive "
    "help and how each service is built. Prefer facts from resolved incidents over guesses."
)
...
self.client.create_bank(
    bank_id=self.bank_id,
    name="Recurrence on-call memory",
    mission=BANK_MISSION,
    disposition={"skepticism": 4, "literalism": 4, "empathy": 2},
)
```

High skepticism, because a weak match should not be treated as "this is definitely INC-2041". High literalism, because the exact command matters at 8 pm. Low empathy, because nobody on a SEV1 bridge wants reassurance; they want the PID query. The [Hindsight docs](https://hindsight.vectorize.io/) explain how disposition shapes `reflect`. I found it a nicer lever than adding more and more system-prompt instructions.

[SCREENSHOT: the bank in the Hindsight Cloud UI, showing the mission and memory count]

## Splitting dead ends out

Here is the core of it, from `recurrence/seed.py`. Each incident becomes a narrative memory, and if it has a `did_not_work` field, a *second* memory:

```python
if inc.get("did_not_work"):
    items.append(
        {
            "content": (
                f"During {inc['id']} on {inc['service']} this did NOT work and should not be repeated: "
                f"{inc['did_not_work']}"
            ),
            "timestamp": inc["resolved_at"],
            "context": f"failed remediation attempt on {inc['service']}",
            "document_id": f"{inc['id']}-dead-end",
            "tags": base_tags + ["kind:dead-end"],
            "metadata": {**meta, "kind": "dead-end"},
        }
    )
```

Why not leave it in the narrative? Three reasons.

**Recall is about relevance, and a long narrative is about many things.** The INC-2041 narrative covers the alert, logs, the migration SQL, the root cause, the fix and the time to mitigate. A query about "payments-api 5xx Hikari pool restart pods" should match the dead end directly. A short, focused item does that better than one paragraph inside a long one.

**The model treats the two kinds of text differently.** Text inside a "Fix that worked" narrative tends to get paraphrased as advice. A separate item that starts with "this did NOT work and should not be repeated" gets read as a warning. Our system prompt says "List any fix that did NOT work so the engineer skips it", and it works noticeably better with that phrasing coming back from recall.

**It keeps working after the incident closes.** The same split runs live. When an engineer fills in "What did NOT work" in the Close-the-loop form, `agent.resolve()` retains it as its own `kind:dead-end` item with a stable `document_id` (`INC-…-dead-end`). The next page recalls the warning on its own.

## Preferences are memories too

The other kind of memory that changes the answer is *who* is asking. Priya, the payments lead, wants rollback-first answers with copy-pasteable `kubectl`/`psql`, not links to dashboards. Arjun, three months into on-call, wants one step at a time, with a line on why it matters and a "how to verify it worked" check after each. Neha wants PromQL she can paste into Grafana.

These are retained with an `engineer:<slug>` tag and recalled with a second, smaller, tag-scoped query, separate from the incident recall. Keeping the two recalls apart stops preferences from being pushed out by long incident narratives, and stops one engineer's preferences leaking into another's answer.

## Before and after

The demo page: payments-api 5xx 19.2%, Hikari pool 40/40 with 201 waiting, a Postgres lock wait on relation 16502. On call: Arjun.

**Memory off:** a general checklist. Roll back if a deploy lines up, check dashboards, *restart unhealthy pods*, *scale out*, escalate. (Paste your own live output.)

**Memory on:** (paste your own live output) names INC-2087 and INC-2041 with their ages, gives the `pg_stat_activity` lock query and `pg_terminate_backend`, says to roll back ledger-svc, and then the line I care about: *do not restart payments-api pods or scale the HPA; both made it worse last time.* It writes the steps the way Arjun asked for them, and points out Priya's standing request to be paged at once for this pattern.

[SCREENSHOT: the memory-on answer with the "Do NOT repeat" line highlighted, and the dead-end memory in the recall panel]

Across our demo alerts, the dead-end memory appeared in recall for <RESULT_FROM_EVAL> of the pages that had one.

## What didn't work for me

**Too many kinds is its own problem.** I briefly had separate kinds for "mitigation", "permanent fix" and "action item". The model started treating action items ("migrations must set `lock_timeout = '3s'`") as things to do *now*, in the middle of an incident. I folded them back into the narrative.

**Retaining the agent's own advice is double-edged.** Recurrence retains what it advised after every page, tagged `kind:advice` with the context "not yet confirmed as the fix". That's useful (the second page of the night knows what was already suggested), but unconfirmed advice is still a memory. Until someone closes the loop, the bank holds a guess. I'd like recall to down-weight `kind:advice` that was never confirmed, and that is still to do.

**Limitation: dead ends are only as honest as the people writing them.** Postmortem culture decides how good this memory is. If the team records "restarted pods" as a step in the fix instead of something that didn't work, the agent will repeat it.

## Takeaways

1. Model failures as their own memories, with wording that makes it clear they are warnings.
2. Use one bank with tags rather than many banks; incidents cross service lines.
3. Use the bank's mission and disposition before piling instructions into the prompt.
4. Recall preferences separately from incidents, with a small token budget.
5. Keep the number of memory kinds small; each one is something the model has to interpret.

If you want the background on why this kind of memory matters, Vectorize's explainer on [agent memory](https://vectorize.io/what-is-agent-memory) is a good start, and [Hindsight is open source](https://github.com/vectorize-io/hindsight). Our code is at <REPO_URL>.

<CODE_IN_LINE: one honest sentence tagging Code.in. If you did not use it, write a neutral mention rather than claiming you did.>
