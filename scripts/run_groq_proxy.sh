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

echo "Starting with Groq via proxy: $GROQ_PROXY_URL"
echo "Open: http://127.0.0.1:$APP_PORT"
exec .venv/bin/python app.py
