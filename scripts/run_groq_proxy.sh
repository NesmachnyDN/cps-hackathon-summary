#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export LLM_PROFILE=groq
export GROQ_PROXY_URL="${GROQ_PROXY_URL:-http://127.0.0.1:10809}"
export APP_PORT="${APP_PORT:-8001}"

if compgen -G "$PWD/official_documents_inbox/original/*.doc" >/dev/null || compgen -G "$PWD/official_documents_inbox/original/*.docx" >/dev/null; then
  .venv/bin/python scripts/prepare_official_documents.py
fi
if [[ -f "$PWD/official_documents_inbox/official_corpus.json" ]]; then
  export NORMATIVE_CORPUS_PATH="$PWD/official_documents_inbox/official_corpus.json"
fi

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  read -r -s -p "Groq API key: " GROQ_API_KEY
  export GROQ_API_KEY
  echo
fi

existing_pid="$(lsof -tiTCP:"$APP_PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
if [[ -n "$existing_pid" ]]; then
  existing_cwd="$(readlink -f "/proc/$existing_pid/cwd" 2>/dev/null || true)"
  existing_cmd="$(tr '\0' ' ' < "/proc/$existing_pid/cmdline" 2>/dev/null || true)"
  if [[ "$existing_cwd" == "$PWD" && "$existing_cmd" == *".venv/bin/python app.py"* ]]; then
    echo "Stopping previous app instance on port $APP_PORT (PID $existing_pid)"
    kill "$existing_pid"
    for _ in {1..30}; do
      kill -0 "$existing_pid" 2>/dev/null || break
      sleep 0.1
    done
  else
    echo "Port $APP_PORT is occupied by another process; refusing to stop it." >&2
    exit 1
  fi
fi

echo "Starting with Groq via proxy: $GROQ_PROXY_URL"
echo "Open: http://127.0.0.1:$APP_PORT"
exec .venv/bin/python app.py
