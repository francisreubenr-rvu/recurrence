# Reddit link post

**Who posts:** one member, from an account with some history (brand-new accounts often get auto-removed). Suggested: Rohith, after 19:30 IST.
**Where:** r/LLMDevs (first choice) or r/AI_Agents. Other subreddits the guide allows: r/sideproject, r/aimemory. Post in **one** subreddit only; cross-posting the same link everywhere looks like spam.
**Type:** a **Link** post pointing to **one** member's article (the guide says "submit a link to your article"). Suggested: Gopreeth's evals article for r/LLMDevs (it is the most technical and the least promotional), or Aryan's dead-end article for r/AI_Agents.

**Before posting:** read the subreddit's sidebar rules. Some require a flair, ban self-promotion on certain days, or want a top comment explaining the link. Follow them, even if that means using a different subreddit.

## Title options (pick one; no hype, no event name)

1. `Storing failed fixes as separate memories made our on-call agent stop repeating them`
2. `How we tested whether long-term memory actually changed an incident agent's answers`
3. `Our incident agent recommended the exact fix that made the outage worse, so we gave it memory of dead ends`

## Link

`<ARTICLE_URL>`

## Top comment to add right after posting (context, not a sales pitch)

> Author here. Some context: this is an SRE on-call agent we built over a few days, running on synthetic incident data for a made-up payments company, so treat the examples accordingly. Memory is [Hindsight](https://github.com/vectorize-io/hindsight) (retain/recall/reflect), and the model is gpt-oss-120b on Groq with qwen3-32b as a fallback.
>
> The part I'd most like feedback on: we store "what did NOT work" as its own memory item, separate from the incident write-up, so it can be recalled even when the rest of the incident isn't the top match. The evaluation is small (5 alerts) and uses string matching on incident IDs, which has obvious holes; the post goes into them.
>
> Two open questions we haven't solved: (1) how to stop the agent's own unconfirmed advice, which we also retain, from being trusted like a confirmed fix later, and (2) how to measure "avoided a known dead end" without an LLM judge. If you've dealt with either, I'd like to hear how.
>
> Code is here if you want to look: https://github.com/francisreubenr-rvu/recurrence

## Tone rules for replies

- Answer questions directly; agree when a criticism is fair.
- No "check out our project!", no upvote requests, no asking teammates to upvote (vote manipulation breaks Reddit's rules).
- Don't argue with people who dismiss it; thank them and move on.
