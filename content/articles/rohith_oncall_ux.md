<!-- DRAFT for Rohith AD. Angle: product and UX for on-call engineers. Rewrite in your own voice before publishing (see content/README_FIRST.md). Remove this comment, every [SCREENSHOT: ...] marker and every <RESULT_FROM_EVAL> before publishing. -->

# Designing an On-Call Agent for the Engineer Paged at 7:47 PM

Picture the person we designed for. Arjun joined the on-call rotation in September. It is 7:47 pm on a Monday, evening payments peak, and his phone says payments-api is failing one request in five. He has a dashboard, a runbook that says "restart unhealthy pods", and a vague memory that something like this happened before he joined.

Every design decision in Recurrence, our on-call agent, came from asking what Arjun needs in the next 90 seconds. The short answer: he needs the team's memory, not a smarter chatbot. That's why we built it on [Hindsight](https://github.com/vectorize-io/hindsight).

## The problem is not intelligence

When we tested generic LLM answers on our synthetic incident pages, they were *reasonable*: check recent deploys, check dashboards, restart pods, scale out, escalate. A good textbook answer.

At Tamarind Pay (the fictional payments company in our demo), that textbook answer is a trap. Twice in the past seven weeks, a ledger-svc database migration locked a table during peak. Both times, restarting payments-api pods helped for a few minutes, and scaling out made it *worse*, because more pods meant more connections against an already saturated PgBouncer. The second time, the engineer on call did exactly what the runbook said and lost 20 minutes before paging the lead.

So the product question wasn't "how do we make the model smarter?" It was **"how do we make sure the next engineer knows what the last two learned the hard way?"**

[SCREENSHOT: the Recurrence console, empty state, with the demo page loaded]

## One screen, three columns of trust

The console is deliberately one page:

- **Left: the page.** Engineer, service, and the alert with log lines. A dropdown replays the demo pages, and you can paste your own.
- **Middle: the answer.** Under 200 words, the most likely fix first, exact commands.
- **Right: "Recalled from memory".** Every memory the agent used, each with **how long ago** it happened.

That right-hand column is the most important UX decision we made. An on-call engineer shouldn't have to trust the agent; they should be able to *check* it. If the answer says "this repeats INC-2087", the incident is right there: "25 days ago", with its root cause and fix. If memory recalled nothing, the panel says "Nothing similar in memory yet." If memory is off, it says "Memory is off. The agent sees only this page." No mystery.

Under the answer there's a small "Tool calls & errors" panel. When the model decided to call `recall_memory` or `reflect_on_history`, you can see it. When memory or the model failed, you can see that too, instead of an answer that is quietly worse.

[SCREENSHOT: the answer plus the recall panel showing "25 days ago" and "46 days ago" next to INC-2087 and INC-2041]

## Personalisation that stays out of the way

Engineers on the same rotation want different things from a helper, and telling them apart turned out to be easy with memory and very hard without it.

- Priya, the payments lead, wants **rollback first**: the rollback command before any investigation, and copy-pasteable `kubectl`/`psql`, not dashboard links.
- Arjun wants **step by step**, with one line on why each step matters and a "how to verify it worked" check after it.
- Neha, on platform, wants **PromQL** she can paste into Grafana Explore.
- Daniel, on checkout, wants customer impact in **failed checkouts per minute**.

There's a "Teach a preference" box. Type "I prefer step-by-step with a verify check" and it is retained to Hindsight with an `engineer:` tag. On every page, the agent runs a small, separate recall scoped to that tag, and puts the result in the prompt above the incident memories:

```python
pref_hits = self.memory.recall(
    f"How does {engineer} prefer to receive help during incidents?",
    tags=[f"engineer:{slug(engineer)}"],
    max_tokens=600,
)
```

There is no settings page and no profile form. You tell it once, the way you'd tell a colleague, and it remembers. Because it's tag-scoped, Priya's rollback-first preference never leaks into Arjun's answer.

## Before and after, from Arjun's seat

Same page, same model. The only difference is the "Memory ON (Hindsight recall + retain)" toggle.

**Memory off** (abridged; paste your own live output):

> 1. Check recent deploys… 2. Check dashboards… 3. Restart unhealthy pods if errors persist. 4. Scale out if connection usage is high. 5. Escalate to the service owner.

**Memory on** (abridged; paste your own live output):

> This is a repeat of INC-2087 (25 days ago) and INC-2041 (46 days ago): a ledger-svc migration holding a lock on ledger.entries.
> **Step 1:** find the blocking query (`SELECT pid, query FROM pg_stat_activity WHERE wait_event_type='Lock'`). *Why:* … *Verify:* …
> **Step 2:** terminate it with `pg_terminate_backend`… **Step 3:** roll back ledger-svc…
> **Do NOT** restart payments-api pods or scale the HPA; both made it worse last time.
> Priya asked to be paged immediately for this pattern.

For Arjun the difference isn't that the answer is longer. It's that it's *his team's* answer, written the way he asked for it, and it includes the one thing he'd otherwise learn the hard way.

[SCREENSHOT: memory OFF vs memory ON for the same page, with the "Do NOT" line and the step-by-step format visible]

## Closing the loop is the product

The biggest UX risk for a memory-based tool is that nobody feeds it. So the form that makes it learn sits on the same screen as the answer: **"Close the loop (retain the real outcome)"**, with four fields: what happened, root cause, fix that worked, and what did NOT work.

```python
def resolve(self, service, engineer, summary, root_cause, fix, did_not_work="", incident_id=None, now=None):
    """Retain the confirmed outcome of a page. Returns number of memories written."""
```

Behind that button, the outcome becomes one incident memory, and, if you filled in the last field, a separate dead-end memory. The next engineer paged for the same thing gets both. The agent also retains its own advice after every answer, marked as unconfirmed, so a second page the same night knows what was already suggested.

We kept it to four short fields on purpose. A form that asks for a full postmortem at 9 pm, right after an incident, doesn't get filled in.

[SCREENSHOT: the Close the loop form filled in after the demo page]

## What we got wrong, or haven't solved

**The page is pasted, not pushed.** Right now an engineer copies the alert into the console. The real product receives the PagerDuty or Opsgenie webhook and posts into the incident Slack channel. Until then, there's friction at the worst possible moment.

**Time matters more than we expected.** Our first version said "this resembles a past incident." Adding "25 days ago" made answers feel far more trustworthy in our own testing. It cost almost nothing, because Hindsight keeps each memory's timestamp. I'd now treat "when" as a required part of any recalled memory shown to a user.

**Limitation: the agent only knows what the team writes down.** If the loop isn't closed, the next page learns nothing. We think the answer is importing postmortems automatically, not asking harder.

## What I'd tell anyone building an agent for operators

1. Show the memories next to the answer, with their age. Being able to check is what builds trust.
2. Let users teach preferences in plain words, scoped to them.
3. Make "what did NOT work" a first-class field. It's the most valuable thing an incident teaches.
4. Put the learning step on the same screen as the answer, and keep it short.
5. Show failures (memory down, tool errors) instead of quietly answering worse.

For how the memory side works, the [Hindsight docs](https://hindsight.vectorize.io/) are the place to start, and Vectorize's write-up on [agent memory](https://vectorize.io/what-is-agent-memory) explains the idea well. Our code: https://github.com/francisreubenr-rvu/recurrence.

In our live tests, the memory-on answer named the right past incident on <RESULT_FROM_EVAL> of our demo pages (see Gopreeth's post for how we measured it).

<CODE_IN_LINE: one honest sentence tagging Code.in. If you did not use it, write a neutral mention rather than claiming you did.>
