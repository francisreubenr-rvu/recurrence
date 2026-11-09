# Deploying Recurrence

Two targets are supported. They are not equivalent, and the difference matters for what the
demo can honestly claim.

| Target | Memory survives | Live Hindsight + Groq | Use it for |
|---|---|---|---|
| Vercel (Python function, Fluid compute) | No. Every cold start and every instance has its own store. | Possible, but no state affinity: advice written on one instance is invisible to the next. | A stateless showcase of the console and the answer flow. |
| Render / any container host, one worker | Yes, for the life of the process. | Yes. | The real memory demo. |

Vercel is the default here only because it needs no credential beyond the CLI login. The
deployed instance runs with `RECURRENCE_OFFLINE=1`, which means synthetic incident data and a
per-process fake store. Answers come from the offline template, not a language model. The
console says so in a banner; nothing in the response is presented as a Hindsight or Groq result.

## Vercel

Files that make it work, already in the repo:

| File | Why |
|---|---|
| `pyproject.toml` | `[tool.vercel] entrypoint = "app.server:app"`. Without it the builder guesses and a nested `app/` package is ambiguous. |
| `.python-version` | `3.12`. Vercel supports 3.12, 3.13 and 3.14 only. |
| `vercel.json` | `fluid: true`, `maxDuration: 60` on `app/server.py`, and `includeFiles` for `data/incidents.json` and `app/static/` so both are readable inside the function. |
| `.vercelignore` | Keeps `.venv/`, research material and the test suite out of the upload. |

```bash
npx -y vercel@latest link --yes --project recurrence
printf '1\n' | npx -y vercel@latest env add RECURRENCE_OFFLINE preview
npx -y vercel@latest deploy --yes
```

The deploy prints the preview URL. Verify it against the real URL, never against
`vercel dev --local`: with the CLI versions tested here, local mode either serves `index.html`
as a static file with no function built, or builds a function that answers every route with
`502 NO_RESPONSE_FROM_FUNCTION`. A live preview URL is the only proof.

```bash
BASE=https://<deployment>
curl -sS "$BASE/api/health"     # mode "offline", memory "fake-offline"
curl -sS "$BASE/api/state"      # memories_held for this instance
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/"
```

### Live memory on Vercel

Set `GROQ_API_KEY`, `HINDSIGHT_API_URL` and `HINDSIGHT_API_KEY` instead of `RECURRENCE_OFFLINE`,
then seed with `python -m recurrence.seed` against the same bank. Recall and retain still hit the
same bank, but writes land on whichever instance handled the request, and Fluid compute
recycles instances without warning. Do not describe that as a working memory demo.

## Render (or any single-process host)

```bash
docker build -t recurrence .
docker run -p 8000:8000 \
  -e RECURRENCE_OFFLINE=1 \
  recurrence
```

This machine has no container runtime, so the `Dockerfile`, `.dockerignore` and `render.yaml` in
the repo have not been executed. They follow the shape the app needs (Python 3.12, one worker,
`/api/health` as the health check) but treat them as unverified until a build succeeds.

The process is `uvicorn app.server:app --host 0.0.0.0 --port $PORT`, one worker. Running more
than one worker splits the offline store and breaks `POST /api/resolve` visibility, so keep the
worker count at one until a shared backend exists.

## Environment variables that change behaviour

| Variable | Effect |
|---|---|
| `RECURRENCE_OFFLINE` | `1` uses the fake store and the template LLM. |
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODEL` | Live LLM configuration. |
| `HINDSIGHT_API_URL`, `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK_ID` | Live memory configuration. |
| `RECURRENCE_WRITE_TOKEN` | Enables the write routes; without it live mode refuses writes. |
| `RECURRENCE_ASK_RATE_PER_MIN` | Per-client `/api/ask` limit. |
| `RECURRENCE_INGEST_DEDUPE_SECONDS` | Webhook dedupe window. |

`POST /api/admin/reset` re-seeds the offline demo store and is refused in live mode. On Vercel
it only resets the instance that answered the request, which is the honest limit of the platform.

## Rollback

`vercel rollback <deployment-url>` (or `vercel promote` a known-good deployment). Every
deployment is immutable, so a rollback does not need a rebuild.
