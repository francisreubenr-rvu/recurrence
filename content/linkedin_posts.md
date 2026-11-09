# LinkedIn posts (one per member)

Rules (from the official content guide): under **800 characters**, no hashtags or links in the first two lines, 3–5 hashtags on the **last line only** (allowed: #AIAgents #AI #Hindsight #AgentMemory #AIMemory #LLM), **repo link in the post body**, positive mention of Hindsight, tag **Code.in**. Never name the event type in the post, comments or hashtags.

Character counts below were computed with Python `len()` on the exact text in each code block. "With URL" replaces `https://github.com/francisreubenr-rvu/recurrence` with a 54-character stand-in (`https://github.com/<github-user>/recurrence-oncall-memory`). Re-count after you paste the real URL and rewrite in your own voice (`python3 -c "print(len(open('post.txt').read()))"`). LinkedIn counts a little differently (line breaks, and the @mention turns into the page name), so keep about 30 characters of headroom.

**How to tag Code.in:** type `@Code` in the LinkedIn editor and pick the Code.in company page from the dropdown so it becomes a real mention. If the page doesn't come up, leave `Code.in` as plain text. **Only say you built with it if you actually used it**; otherwise change the line to something true.

Before you publish, check every claim against the live run (for example, "20 days earlier" in the evals post assumes the learning-curve run behaves as designed).

## Francis Reuben R (architecture)

Characters: **726** as written; **773** with a 54-char repo URL. Limit 800.

```text
Most AI incident assistants give the same advice on page 1 and page 100.

Ours gave advice that had already made the same outage worse. Twice.

So we built Recurrence, an on-call agent with long-term memory, on Hindsight.

What changed:
- Before: "restart pods, scale out."
- After: "Repeat of INC-2087, 25 days ago. Kill the migration lock, roll back. Do NOT restart or scale; both made it worse."

What I'd copy:
1. Recall before the LLM call, then give it recall as a tool too
2. Keep timestamps on memories; "how long ago" builds trust
3. If memory is down, still answer

Hindsight agent memory made this a small layer, not a project.

Code: https://github.com/francisreubenr-rvu/recurrence
Built with help from @Code.in

#AIAgents #AgentMemory #Hindsight #LLM
```

## Aryan Dubey (dead-end memories)

Characters: **676** as written; **723** with a 54-char repo URL. Limit 800.

```text
The most useful line in a postmortem is the one nobody rereads:

"What we tried that didn't work."

In Recurrence, our on-call agent, failed fixes are first-class memories in Hindsight.

How:
- Each incident is retained twice: the narrative, plus a separate "did NOT work" item tagged kind:dead-end
- One bank for the team; tags scope service, engineer, kind
- Bank mission + disposition instead of a bloated prompt

Before: "restart the pods."
After: "Do NOT restart pods or scale the HPA. Both made INC-2087 worse."

Choosing Hindsight agent memory let us model "what not to do" in an afternoon.

Repo: https://github.com/francisreubenr-rvu/recurrence
Thanks @Code.in

#AIAgents #AgentMemory #Hindsight #AIMemory
```

## Gopreeth Saharsh (evals)

Characters: **639** as written; **686** with a 54-char repo URL. Limit 800.

```text
"Our agent has memory" is a claim. Here is how we tested it.

Recurrence is an on-call agent built on Hindsight. Memory is one switch: same model, same prompt, same page.

What we measured:
1. recall_hit: did Hindsight return the right past incident?
2. answer_cites: did the model actually use it?
3. Learning curve from an EMPTY bank: interaction 1 vs 5

Interaction 1: generic triage.
Interaction 5: names the outage from 20 days earlier and skips the fix that failed.

Tips:
- Pin "now" per test case
- Run memory-off first
- Never quote offline numbers

Results + code: https://github.com/francisreubenr-rvu/recurrence
With @Code.in

#AIAgents #Hindsight #AgentMemory #LLM
```

## Rohith AD (on-call UX)

Characters: **612** as written; **659** with a 54-char repo URL. Limit 800.

```text
At 7:47 PM, an on-call engineer doesn't need a smarter chatbot.

They need what the last two engineers learned the hard way.

Recurrence is an on-call agent built on Hindsight agent memory. UX choices that mattered:

- Show recalled incidents next to the answer, with "25 days ago"
- Teach preferences in plain words ("step by step, with a verify check"), scoped per engineer
- "What did NOT work" is its own field when closing an incident

Before: restart pods, scale out.
After: repeat of INC-2087; kill the lock, roll back, don't scale.

Code: https://github.com/francisreubenr-rvu/recurrence
Thanks @Code.in

#AIAgents #AgentMemory #Hindsight #AI
```

## Comments (post both, in this order, right after publishing)

The guide says both "post the article URL as the first comment" and "add a comment with the Hindsight GitHub link". We post two comments to meet both.

**Comment 1 (article):**

```text
I wrote up the details here: <ARTICLE_URL>
```

Alternatives: `Full write-up, with code and the before/after: <ARTICLE_URL>` / `The article behind this post: <ARTICLE_URL>`

**Comment 2 (Hindsight):**

```text
Here's a link to Hindsight if you want to check it out: https://github.com/vectorize-io/hindsight
```

Alternatives (wording from the official guide): `Try Hindsight here: https://github.com/vectorize-io/hindsight` / `Want to learn more? Here is the repo: https://github.com/vectorize-io/hindsight`
