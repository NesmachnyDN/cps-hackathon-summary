#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export LLM_PROFILE=groq
export GROQ_PROXY_URL="${GROQ_PROXY_URL:-http://127.0.0.1:10809}"
export APP_PORT="${APP_PORT:-8001}"

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  read -r -s -p "Groq API key: " GROQ_API_KEY
  export GROQ_API_KEY
  echo
fi

echo "Starting with Groq via proxy: $GROQ_PROXY_URL"
echo "Open: http://127.0.0.1:$APP_PORT"
exec .venv/bin/python app.py
