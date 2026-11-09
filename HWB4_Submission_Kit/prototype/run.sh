#!/usr/bin/env bash
# Recurrence helper.
#   ./run.sh test       run the pytest suite (offline, no keys)
#   ./run.sh offline    start the console with fake memory + template answers (no keys)
#   ./run.sh seed       seed the Hindsight bank from data/incidents.json (needs .env)
#   ./run.sh serve      start the console against Hindsight + Groq (needs .env)
#   ./run.sh eval       before/after eval (add --offline for the plumbing check)
#   ./run.sh curve      interaction 1 -> 5 learning curve from an empty bank
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
cmd="${1:-serve}"; shift || true
case "$cmd" in
  test)    python -m pytest -q "$@" ;;
  offline) RECURRENCE_OFFLINE=1 python -m uvicorn app.server:app --port "$PORT" ;;
  seed)    python -m recurrence.seed "$@" ;;
  serve)   python -m uvicorn app.server:app --port "$PORT" ;;
  eval)    python -m evals.before_after "$@" ;;
  curve)   python -m scripts.learning_curve "$@" ;;
  *) echo "unknown command: $cmd (test|offline|seed|serve|eval|curve)"; exit 1 ;;
esac
