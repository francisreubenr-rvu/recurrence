# START HERE: Recurrence submission kit

**Deadline: Mon 09 Nov 2026, 23:59 IST.** Internal target: final form submitted by **23:00 IST** (one hour of buffer).

Team: Aryan Dubey, Francis Reuben R, Gopreeth Saharsh, Rohith AD. Team name: `<TEAM_NAME>` (still to be decided; it goes on the final form).

Folder map (as reorganised for the public repository):

| Folder | What is in it |
|---|---|
| repository root | The code: `recurrence/`, `app/`, `evals/`, `scripts/`, `tests/`, `data/`. Another person was editing the prototype; this kit did not touch the code. |
| `docs/internal/` | This file: plan, rubric, checklist, rule conflicts, form answers, profile review note. |
| `content/` | `README_FIRST.md`, four article drafts, four LinkedIn posts, one Reddit post. |
| `video/` | Script, shot list, thumbnail brief, YouTube title/description/tags. |

---

## 1. The problem statement (official, short version)

Build an AI agent on **Hindsight** (Vectorize's agent memory: `retain`, `recall`, `reflect`) that remembers, recalls and gets better over time. Memory should be the star, shown as a clear before/after: generic at interaction 1, personalised by interaction 5, able to recall context from days or weeks ago. Avoid student-centric ideas; target a real business workflow. **Incident Response Agent** is one of the listed Engineering & DevOps ideas: "Remembers past incidents, their root causes, resolution steps, and which runbooks worked."

Also required by the problem statement: use Hindsight; **download and use Band AI desktop** (https://www.band.ai); a GitHub repo with clean, documented code; a demo video; a live demo to judges; content from every member (article, social post, video); and an explanation of how Hindsight memory is used.

## 2. Pitch paragraph

> **Recurrence is the on-call agent that remembers every outage.** At 7:47 pm a page fires at Tamarind Pay (a fictional payments company): payments-api is throwing 5xx, the Hikari pool is exhausted, and the on-call engineer has been on the rotation for two months. A stateless assistant tells him what every runbook says: restart the pods, scale out. Both of those made things worse 25 days ago. Recurrence pulls that incident (INC-2087) and the one 46 days ago (INC-2041) out of its Hindsight memory bank. It says this is the third time a ledger-svc migration has locked `ledger.entries`, gives the `pg_terminate_backend` and rollback commands, and warns him off the two dead-end fixes. It also writes the steps the way this engineer asked to get them: one at a time, each with a "how to verify" check. When the incident closes, the real root cause, the fix and what failed go back into memory, so the next page starts smarter. Built on Hindsight (retain / recall / reflect) with a Groq-hosted open model (`openai/gpt-oss-120b`, falling back to `qwen/qwen3-32b`).

## 3. Rubric: how we score and what to show

| Criterion | Weight | Our case | What to make obvious in demo, video and README |
|---|---|---|---|
| Innovation | 30 | Incident memory is a listed idea, so our twist has to carry it: **dead-end memories** (failed fixes stored as their own retrievable items), **per-engineer preferences** scoped by tags, and the agent **retaining its own advice** so the next page knows what was already tried. | Say the phrase "it remembers what did NOT work" early. Show the dead-end warning on screen. |
| Use of Hindsight memory | 25 | Memory is the product. One bank with a mission and disposition; `retain_batch` for seeding; tag-scoped `recall` (`service:`, `engineer:`, `kind:`); `reflect` exposed as a tool; outcomes retained through "Close the loop". The `Memory ON` toggle gives a one-click before/after. | Toggle OFF/ON on the same page. Show the "Recalled from memory" panel with "25 days ago" / "46 days ago". Run `scripts/learning_curve.py` (interaction 1 vs 5). |
| Technical implementation | 20 | A small backend interface (Hindsight vs offline fake), defensive Groq tool-calling (`tool_use_failed` → fallback model → no-tools answer), and memory failure that never blocks the answer. FastAPI, tests, and an eval script. | README architecture diagram; mention the error handling; tests pass; eval run with real numbers (`<RESULT_FROM_EVAL>`). |
| User experience | 15 | One screen: page in, answer out, memories with their age on the right, a close-the-loop form, and a teach-a-preference box. | A tight 4-minute video with a story: one engineer, one evening. |
| Real-world impact | 10 | Repeat incidents and repeated failed fixes are a real on-call cost; postmortems are written and then not read. Path to adoption: PagerDuty/Opsgenie webhook in, Slack out, postmortem import. | One slide or line on the adoption path. No invented market numbers. |

Honest weak spots: the data is synthetic (it says so); there is no real pager integration yet; the eval set is small (5 demo alerts). Say all of this plainly instead of letting a judge find it.

## 4. Hour-by-hour plan: Mon 09 Nov 2026 (all times IST)

Owners: **A-team (code and submission)** = Francis + `<MEMBER_B>` (suggested: Gopreeth, since his article is the evals one). **V-team (video)** = the other two (suggested: Aryan + Rohith). Swap names if the team prefers; just write them in here.

| Time (IST) | Owner | Task | Done when |
|---|---|---|---|
| 06:00–06:30 | All four | Read this file and `content/README_FIRST.md`. Agree on the team name and the A-team / V-team split. Everyone downloads **Band AI desktop**. | Team name written here; owners confirmed |
| 06:30–07:30 | Francis | Hindsight Cloud account (ui.hindsight.vectorize.io), apply promo credits in Billing, create API key. Groq API key. Put both in `.env` only, never in git. | `GET /api/health` shows `memory: hindsight`, `llm: groq` |
| 06:30–07:30 | `<MEMBER_B>` | Create the public GitHub repo, add `.gitignore` (`.env`), push the current prototype. | Repo URL pasted into `docs/internal/final_form_answers.md` |
| 06:30–08:00 | V-team | Read `video/script.md`, run the app locally in offline mode to rehearse the clicks, set up OBS/Loom at 1080p with large fonts. | One rehearsal recorded (throwaway) |
| 07:30–09:00 | Francis + `<MEMBER_B>` | Live run: `python -m recurrence.seed`, then `python -m evals.before_after --no-seed`, then `python -m scripts.learning_curve`. Save outputs and screenshots. | Real numbers available for every `<RESULT_FROM_EVAL>` |
| 09:00–09:30 | Francis | Send real eval numbers and screenshots to everyone (team chat). | Everyone has the numbers |
| 09:00–11:00 | `<MEMBER_B>` | README: what it is, the architecture diagram, how Hindsight is used (bank, tags, retain/recall/reflect), setup, offline mode, eval results, limitations, and a link to Hindsight. Push. | README renders on GitHub |
| 09:30–12:30 | V-team | Record the live demo against the real Hindsight bank (Francis's `.env`, or screen-share from his machine). Record the talking-head intro and outro. | Raw footage saved |
| 10:00–13:00 | Each person | Rewrite your article draft in your own voice, insert real numbers and screenshots. | Draft ready to publish |
| 12:30–16:00 | V-team | Edit the video (3:30–4:30), captions on the key lines, thumbnail (`video/thumbnail.md`). | Exported 1080p MP4 + thumbnail PNG |
| 13:00–14:30 | Lunch / buffer | | |
| 14:30–16:00 | Each person | Publish your article (Medium / Dev.to / Hashnode / LinkedIn Article). Tag Code.in. Check the links. | Public URL works in an incognito window |
| 16:00–16:45 | V-team | Upload to YouTube (public, with thumbnail, using `video/youtube_meta.md`). | Public URL works logged out |
| 16:00–18:00 | Francis + `<MEMBER_B>` | Final code polish: tests pass, offline mode works, repo description and topics set, YouTube link in README. | Clean clone runs from README alone |
| 17:00–19:30 | Each person | Publish your LinkedIn post (repo link in the post, Code.in tagged). First comment: article URL. Second comment: the Hindsight GitHub link. See the rule conflicts below. | Post + both comments live |
| by 20:00 | All four | **Article + LinkedIn post live for every member.** | Four article URLs + four post URLs collected in the form file |
| 19:30–20:30 | One person (suggested: Rohith) | Reddit link post (`content/reddit_post.md`). Check the subreddit's rules first. | Reddit URL collected |
| 20:00–21:30 | All four | Profile Review Forms (`docs/internal/profile_review_note.md`), each person their own. | Each person confirms submitted |
| 21:30–22:30 | Francis | Fill in the final form from `docs/internal/final_form_answers.md`. Second person reads every link back. | All fields filled, not yet submitted |
| 22:30–23:00 | Francis + one reviewer | Run the pre-submit checklist below and submit. | **Submitted by 23:00 IST** |
| 23:00–23:59 | Buffer | Fix anything broken. Do not start new work. | |

Live demo to judges: whenever it is scheduled, use the same flow as `video/script.md`. Have offline mode ready as a backup (`RECURRENCE_OFFLINE=1`), and say clearly if you fall back to it.

## 5. Pre-submit checklist

**Repo**
- [ ] Public; README explains how Hindsight memory is used (bank, tags, retain / recall / reflect, close-the-loop)
- [ ] `.env` not committed; `.env.example` present; no keys in history
- [ ] Setup steps work from a clean clone; tests pass; offline mode is labelled as offline-only
- [ ] Synthetic data clearly labelled as fictional
- [ ] YouTube link in the README

**Content, per member (×4)**
- [ ] Article public and linkable, **800–1,500 words** (see conflict 3), title about the idea and not the event
- [ ] Contains the three links: github.com/vectorize-io/hindsight, hindsight.vectorize.io, vectorize.io/what-is-agent-memory
- [ ] At least one real code snippet, one before/after, one honest limitation, screenshots
- [ ] No `<RESULT_FROM_EVAL>` or `[SCREENSHOT: ...]` left in the published text
- [ ] Code.in tagged or mentioned
- [ ] LinkedIn post under 800 characters, repo link in the body, 3–5 allowed hashtags on the last line, Code.in tagged
- [ ] Comments: article URL + Hindsight GitHub link
- [ ] Your own Profile Review Form submitted

**Team**
- [ ] YouTube video public, 2–5 min, 1080p, thumbnail set
- [ ] Reddit link post live in an allowed subreddit
- [ ] Every member has Band AI desktop downloaded
- [ ] Final form submitted by 23:00 IST

**Banned word check, the one that disqualifies.** The guide disqualifies any article or social post that contains the name of this kind of event (the word that starts with "hack" and ends with "athon"), including in hashtags. Before publishing, search your article, post, comments, YouTube title, description and tags for it (Ctrl+F "athon"). Also no Google Drive links anywhere: video goes on YouTube, articles go on a blog platform.

## 6. Rule conflicts found in the official documents

| # | Conflict | Where | What we do |
|---|---|---|---|
| 1 | **First comment.** The LinkedIn prompt's "YOUR TURN" box says "Post the article URL as the first comment." Step 6 says to add a comment with the Hindsight GitHub link, and the summary table says "Add a first comment linking to Hindsight Github repo." | Content guide, Part 2 | Post **two** comments: first the article URL, then right after it the Hindsight GitHub link. Both instructions are then met as closely as possible. Optionally put the article URL in the post body too, if it still fits under 800 characters. |
| 2 | **Code.in tag on articles too.** The very end of the guide says "Tag Code.in on LinkedIn and Articles", but neither the article prompt nor the article checklist mentions it. | Content guide, last line | Tag Code.in in the LinkedIn post and add one honest line in each article (for example, which coding agent we used for what). If we did not use Code.in for anything, write a neutral acknowledgement instead of claiming we used it. Mention it in the article; tag it where the platform supports tags. |
| 3 | **Article length.** The overview table and quick reference say 800–1,500 words; Prompt 2 asks for 1,200–2,000. | Content guide, Part 1 | Aim for **1,200–1,500 words**, which meets both. Drafts here are around 1,300–1,500. |
| 4 | **Video per member or per team.** The problem statement says all team members must complete an article, a social post **and a video**; the content guide says one video per team. | Problem statement vs content guide | One team video (the guide is more specific). Each member appears or is credited in it, and if anyone has time they can post a short personal clip. Ask the organisers on Slack if unsure. |
| 5 | Minor: the quick-reference table says Prompt 1 gives 5 titles, but Prompt 1 asks for 20; it numbers prompts 1–5 while the text says 6. | Content guide | No action needed. |
| 6 | Minor: Prompt 2 says to describe the project as finished and production-ready, while the grounding rules say not to claim results that the code does not show. | Content guide | Describe the design as it is, put no invented numbers in, and label synthetic data as synthetic. |
