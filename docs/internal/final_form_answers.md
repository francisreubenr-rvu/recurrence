# Final submission form: answers

Fill in every `<...>` before 22:30 IST. Submit by **23:00 IST** (hard deadline 23:59 IST, Mon 09 Nov 2026).
Before you paste a link, open it in a logged-out or incognito window. If the form asks for one link per field and we have four (articles and posts), put each member's link on its own line in the order below, or follow the form's own format if it gives one.

| Field | Answer |
|---|---|
| Contact email | `<SUBMITTER_EMAIL>` (whoever submits; use the address registered for the event) |
| Phone | `<SUBMITTER_PHONE>` |
| Team name | `<TEAM_NAME>` |
| Team member names | Aryan Dubey; Francis Reuben R; Gopreeth Saharsh; Rohith AD |
| Project name | Recurrence: the on-call agent that remembers every outage |
| GitHub repository | `https://github.com/francisreubenr-rvu/recurrence` |
| LinkedIn post(s) | Aryan: `<LINKEDIN_POST_URL_ARYAN>`<br>Francis: `<LINKEDIN_POST_URL_FRANCIS>`<br>Gopreeth: `<LINKEDIN_POST_URL_GOPREETH>`<br>Rohith: `<LINKEDIN_POST_URL_ROHITH>` |
| Article(s) | Aryan: `<ARTICLE_URL_ARYAN>`<br>Francis: `<ARTICLE_URL_FRANCIS>`<br>Gopreeth: `<ARTICLE_URL_GOPREETH>`<br>Rohith: `<ARTICLE_URL_ROHITH>` |
| YouTube video | `<YOUTUBE_URL>` |
| Reddit post | `<REDDIT_URL>` |
| Feedback | See the suggested paragraph below (edit before pasting) |

If the form has a "short description" or "how is Hindsight used" field, use this:

> Recurrence is an SRE on-call agent for a fictional payments company, Tamarind Pay. Every incident's alert, logs, root cause and working fix is retained into one Hindsight memory bank, and every fix that did *not* work is retained as its own item, so it can be recalled on its own. Each engineer's preferences are retained with an `engineer:` tag. When a page fires, the agent recalls similar past incidents and that engineer's preferences, and a Groq-hosted model answers with them in context. It can also call `recall` and `reflect` as tools. After the page, the agent retains its own advice, and the "Close the loop" form retains the confirmed root cause, fix and dead ends. With memory off, it gives generic runbook advice. With memory on, it names the incident from 25 days ago, warns against the restart and scale-out that made it worse last time, and formats the steps the way the engineer asked.

## Suggested feedback paragraph (edit; keep it true)

> Hindsight made it easy to keep the memory design simple: one bank, with tags for service, engineer and memory kind, and a mission plus disposition that told the bank what to prioritise. `retain_batch` made seeding fast. The temporal side of recall was the most useful part for us, because "this happened 25 days ago" is exactly what an on-call engineer needs to hear. Things that would have helped: more examples of tag-scoped recall combined with `tags_match` modes, guidance on modelling "negative" knowledge (fixes that did not work) so it is not mixed up with positive fixes, and a short note on expected retain-to-recall latency when seeding a fresh bank. On the event side, a single checklist that resolved the small differences between the problem statement and the content guide (article length, which link goes in the first LinkedIn comment, video per team vs per member) would have saved time. `<ADD ONE THING FROM YOUR OWN EXPERIENCE>`

Before pasting, remove any sentence that does not match what you actually experienced.

## Final check before pressing submit

- [ ] Every link opens logged out
- [ ] No Google Drive links anywhere
- [ ] Team name matches what was registered
- [ ] Screenshot of the submitted form saved
