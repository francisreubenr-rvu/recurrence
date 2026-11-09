# Video script: "Recurrence: the on-call agent that remembers every outage"

Target length **3:30–4:30** (the guide allows 2–5 minutes). 1080p screen recording + talking head for the intro and outro. Speak naturally; **don't read this word for word.**

**Setup before recording**
- App running against the **live** Hindsight bank and Groq: `uvicorn app.server:app --port 8000`. Header must show `memory: hindsight` and `llm: groq`. If you are forced to use offline mode, the header shows `fake-offline` / `offline-template`: say so out loud on camera, or re-record.
- Bank seeded: `python -m recurrence.seed`.
- Browser zoom 125–150%, terminal font 18pt or larger, notifications off, `.env` never on screen.
- Demo page: replay dropdown → **"Day 0: today's page (the one in the video)"** (DEMO-1: Arjun Mehta, payments-api, Mon 09 Nov 2026, 7:47 PM IST).
- Have the learning-curve output ready: `python -m scripts.learning_curve` (it uses its own bank, `<bank>-curve`, starting empty).

| Time | On screen | Voiceover (natural, adapt freely) | Who |
|---|---|---|---|
| 0:00–0:20 | Talking head, or a team photo with names | "Hi, we're Aryan, Francis, Gopreeth and Rohith. We built Recurrence: an on-call agent that remembers every outage, including the fixes that didn't work." | Any |
| 0:20–0:40 | Recurrence console, empty. Title card: "Tamarind Pay: a fictional payments company" | "Here's the setup. Tamarind Pay is a made-up payments company with seven weeks of realistic, synthetic incident history: twelve incidents across six services. Memory is Hindsight, and the model is gpt-oss-120b on Groq." | Narrator |
| 0:40–1:10 | Pick the "Day 0" page. Zoom into the alert: 5xx 19.2%, Hikari 40/40 with 201 waiting, AccessExclusiveLock wait. Engineer: Arjun Mehta. | "It's 7:47 pm on a Monday. payments-api is failing one request in five. The on-call is Arjun, who joined the rotation in September. First, memory **off**." | Narrator |
| 1:10–1:40 | Untick "Memory ON". Click **Ask Recurrence**. Highlight "restart pods" and "scale out" in the answer. Right panel: "Memory is off. The agent sees only this page." | "That's a reasonable textbook answer: check deploys, restart pods, scale out. At this company, restarting and scaling are exactly what made this outage worse. Twice. The model can't know that, because it only sees this page." | Narrator |
| 1:40–2:30 | Tick "Memory ON". Ask again. Pan slowly to "Recalled from memory": **INC-2087, 25 days ago** and **INC-2041, 46 days ago**, plus the dead-end memory. Then to the answer. | "Same page, same model, memory on. It recalls INC-2087 from 25 days ago and INC-2041 from 46 days ago: a ledger-svc migration locking `ledger.entries`. It gives the lock query, `pg_terminate_backend` and the rollback. Look at this line: *do NOT restart pods or scale the HPA*. We store failed fixes as separate memories, so they come back on their own." | Narrator |
| 2:30–2:55 | Zoom into the answer's format: numbered steps with a "verify" check after each. Show the preference memory in the panel. Show "Tool calls & errors" if the model called `recall_memory` / `reflect_on_history`. | "It also answers the way Arjun asked to be helped, one step at a time with a 'how to verify' check, because his preference is a memory too, tagged to him. And it says Priya, the payments lead, wants to be paged straight away for this pattern." | Narrator |
| 2:55–3:25 | Scroll to **"Close the loop"**. Fill in: what happened / root cause / fix / **what did NOT work**. Click **Retain outcome**. Show `retained: 2`. | "When the incident's over, Arjun closes the loop: root cause, the fix, and what didn't work. That's two memories, one incident and one dead end, so the next engineer starts smarter." | Narrator |
| 3:25–3:55 | Terminal: `python -m scripts.learning_curve`. Show interaction 1 (nothing to recall, generic) then interaction 5 (recalls the 20 Oct outage, warns about restart/scale, step-by-step format). | "And this is learning from an empty bank. Interaction 1 has nothing to remember. Four pages and one stated preference later, interaction 5 knows the outage from 20 days earlier, the failed fixes, and how this engineer likes his answers." | Narrator |
| 3:55–4:10 | Code: `recurrence/seed.py`, the `did_not_work` block; `recurrence/memory.py` `recall(...)`. Optional: eval summary with real numbers. | "Under the hood it's one Hindsight bank with tags for service, engineer and kind. We retain incidents, dead ends and preferences, recall them before the model call, and expose recall and reflect as tools." *(If live eval numbers exist: "On our demo alerts, memory-on named the right past incident in <RESULT_FROM_EVAL>.")* | Narrator |
| 4:10–4:30 | Talking head. End card: repo URL, Hindsight GitHub link. | "What surprised us: the most valuable memory wasn't the fix, it was what *didn't* work. Code's in the description, along with Hindsight. Thanks for watching." | Any |

**Recording notes**
- If the live answer wording differs from the voiceover, describe what is actually on screen. Never narrate something the screen doesn't show.
- Days-ago values assume the page's `now` of 09 Nov 2026, 7:47 PM IST (INC-2087 opened 15 Oct, INC-2041 opened 24 Sep).
- If the LLM call fails during recording, the console still shows the recalled memories; say so and move on, or re-take.
- Don't show the `.env` file, API keys, or the Hindsight Cloud API keys page.
