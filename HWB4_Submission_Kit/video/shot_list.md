# Shot list

Record each shot as its own clip; it makes editing faster. 1080p minimum, 30 fps. Use OBS, Loom, or a Filmora trial for screen + camera.

| # | Shot | Type | Length | Must be visible | Notes |
|---|---|---|---|---|---|
| 1 | Team intro | Talking head (webcam), or team photo + VO | 0:20 | Faces/names of all four | Good light, quiet room |
| 2 | Console overview | Screen | 0:20 | Header with `memory: hindsight`, `llm: groq`; title "Recurrence" | Title card: "Tamarind Pay is fictional" |
| 3 | Demo page selected | Screen + zoom | 0:30 | Alert text: 19.2%, `total=40, active=40 ... waiting=201`, `AccessExclusiveLock` | Slow zoom on the log lines |
| 4 | Memory OFF answer | Screen | 0:30 | Toggle unticked; "restart pods" / "scale out" in the answer; "Memory is off…" panel | Highlight box on the two bad steps |
| 5 | Memory ON answer | Screen | 0:50 | Toggle ticked; recall panel with INC-2087 "25 days ago", INC-2041 "46 days ago"; dead-end memory; "Do NOT" line | Hold 3 seconds on the recall panel |
| 6 | Preference applied | Screen + zoom | 0:25 | Step-by-step format with verify checks; preference memory; tool trace | Caption: "preference recalled via tag engineer:arjun-mehta" |
| 7 | Close the loop | Screen | 0:30 | Four fields filled; Retain outcome; `retained: 2` | Type quickly or paste |
| 8 | Learning curve | Terminal | 0:30 | Interaction 1 header + generic answer; interaction 5 header + recalled memories + answer | Font 18pt or larger; cut the waiting time |
| 9 | Code glimpse | Editor | 0:15 | `seed.py` dead-end block; `memory.py` `recall` | Dark theme, big font |
| 10 | Eval numbers (optional) | Terminal | 0:10 | Summary JSON from the live run | Only if live numbers exist |
| 11 | Outro | Talking head + end card | 0:20 | `<REPO_URL>`, github.com/vectorize-io/hindsight | End card 5 seconds or more |

Total ≈ 4:20 before trimming. If it runs over 4:30, cut shot 9 or 10 first.

**Editing checklist**
- [ ] Captions on the three key lines: "Memory OFF", "25 days ago", "Do NOT restart or scale"
- [ ] No keys, `.env`, emails or notifications visible in any frame
- [ ] Audio levelled; remove long silences
- [ ] Export 1080p MP4
- [ ] Watch the whole thing once before uploading
