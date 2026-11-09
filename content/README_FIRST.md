# README FIRST: before you publish anything

These are **drafts**, written quickly so nobody starts from a blank page. They are not yours yet.

## 1. Rewrite your draft in your own voice

- The articles, LinkedIn posts and Reddit text were drafted for you. **Each member must rewrite their own** so it sounds like them, and so the four articles don't read as if one person wrote them all. The official guide says: "The best articles sound like a real person wrote them. Edit the AI output until it sounds like you."
- Add something only you know: what you actually built, what broke for you, what surprised you. One true paragraph from your own experience is worth more than the whole draft.
- Delete any claim that isn't true for you. For example, if a draft says "in our own testing" about something you didn't see, change or remove it.

| Member | Draft |
|---|---|
| Francis Reuben R | `articles/francis_architecture.md` (architecture, failure handling) |
| Aryan Dubey | `articles/aryan_dead_end_memory.md` (memory design, dead-end memories) |
| Gopreeth Saharsh | `articles/gopreeth_before_after_evals.md` (before/after evaluation) |
| Rohith AD | `articles/rohith_oncall_ux.md` (product and UX for on-call) |
| Everyone | `linkedin_posts.md` (your post plus the two comments) |
| One person | `reddit_post.md` |

## 2. Replace every placeholder

- `<RESULT_FROM_EVAL>`: numbers from the **live** run only (Hindsight + Groq). Francis sends them round about 09:30 IST. **Never invent a number. Never quote the offline/fake mode.** If a number isn't available, delete the sentence.
- "Memory off / memory on" example answers are **abridged sketches**. Replace them with the real output from the live run.
- `[SCREENSHOT: ...]`: take the screenshot described and insert it; delete the marker.
- `https://github.com/francisreubenr-rvu/recurrence`, `<ARTICLE_URL>`: the real links.
- `<CODE_IN_LINE: ...>`: one honest sentence mentioning or tagging Code.in (the guide says to tag Code.in on LinkedIn **and articles**). Don't claim you used it if you didn't.
- Remove the `<!-- DRAFT ... -->` comment at the top.

## 3. Check the rules yourself

This kit summarises the rules, and it may have missed or misread something. **Read the official content guide and problem statement yourself** before publishing. Things that disqualify or cost points:

- Your article and post must **not** mention the name of this kind of event anywhere: not in the title, the body, the hashtags or the comments. Search for "athon" before you hit publish.
- Article length: aim for **1,200–1,500 words** (the guide says 800–1,500 in one place and 1,200–2,000 in another; 1,200–1,500 meets both).
- The article must be **public**, on Medium / Dev.to / Hashnode / Substack / LinkedIn Articles. No Google Drive links.
- Article must include these three links: https://github.com/vectorize-io/hindsight, https://hindsight.vectorize.io/, https://vectorize.io/what-is-agent-memory
- At least one real code snippet, one before/after, one honest limitation, and screenshots.
- LinkedIn post: under 800 characters, repo link in the post, hashtags only on the last line, Code.in tagged. Comments: article URL, then the Hindsight GitHub link.
- Synthetic data: say it is fictional (Tamarind Pay is invented). Don't present it as a real company or real incidents.

## 4. Don't

- Don't copy another member's article.
- Don't paste API keys or `.env` contents into screenshots. Check every screenshot.
- Don't publish before 14:30 IST unless the live numbers are already in.
