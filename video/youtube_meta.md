# YouTube upload details

**Visibility: Public.** Not "unlisted", not a Google Drive link. Upload the custom thumbnail (custom thumbnails may require a verified channel; verify by phone in YouTube Studio if prompted). Category: Science & Technology. Not made for kids.

## Title (pick one; under 70 characters)

1. `This On-Call AI Remembers Every Outage (Hindsight Memory Demo)`
2. `Our Incident Agent Stopped Repeating Fixes That Failed`
3. `Memory OFF vs ON: an AI On-Call Agent Built on Hindsight`
4. `"Seen This 25 Days Ago": Giving an SRE Agent Long-Term Memory`
5. `How Agent Memory Turns Generic Advice Into Your Team's Runbook`

## Description

```
Recurrence is an on-call agent that remembers every outage: past incidents, root causes, the fixes that worked, the fixes that did NOT work, and how each engineer likes to be helped.

In this demo, the same page (payments-api 5xx, Hikari pool exhausted, a Postgres lock wait) gets two answers:
- Memory OFF: generic advice (restart pods, scale out), the exact steps that made this outage worse before.
- Memory ON: it recalls the same incident from 25 and 46 days earlier, gives the lock-kill and rollback commands, warns against the failed fixes, and formats the steps the way this engineer asked.

Then we close the loop (the real outcome is retained) and show learning from an empty memory bank: interaction 1 vs interaction 5.

Built with:
- Hindsight agent memory (retain / recall / reflect): https://github.com/vectorize-io/hindsight
- Hindsight docs: https://hindsight.vectorize.io/
- What is agent memory: https://vectorize.io/what-is-agent-memory
- Groq (gpt-oss-120b, qwen3-32b fallback)
- Code.in

Code: https://github.com/francisreubenr-rvu/recurrence

Articles from the team:
- Architecture (Francis Reuben R): <ARTICLE_URL_FRANCIS>
- Dead-end memories (Aryan Dubey): <ARTICLE_URL_ARYAN>
- Before/after evals (Gopreeth Saharsh): <ARTICLE_URL_GOPREETH>
- On-call UX (Rohith AD): <ARTICLE_URL_ROHITH>

Tamarind Pay is a fictional company; all incident data in this video is synthetic.

Chapters:
0:00 Intro
0:20 The setup
0:40 The page
1:10 Memory OFF
1:40 Memory ON: recall from weeks ago
2:30 Engineer preferences
2:55 Closing the loop
3:25 Learning curve: interaction 1 vs 5
3:55 How it's built
4:10 Takeaway
```

Update the chapter times to match the final edit (the first chapter must be 0:00, with at least 3 chapters). Remove the "Code.in" line if you didn't use it, or keep it as a neutral mention.

## Tags

```
AI agents, agent memory, Hindsight, Vectorize, LLM, Groq, SRE, incident response, on-call, DevOps, AIOps, long-term memory, RAG, gpt-oss, postmortem
```

Do not use any tag that names the event type or student-related tags.
