#!/usr/bin/env bash
# Sobe o Motion Studio em http://localhost:8000
set -e
cd "$(dirname "$0")"
[ -d .venv ] && source .venv/bin/activate
if [ "${MOTION_LLM:-ollama}" != "mock" ] && ! curl -s "${OLLAMA_URL:-http://localhost:11434}/api/tags" >/dev/null; then
  echo "Aviso: Ollama não respondeu em ${OLLAMA_URL:-http://localhost:11434}. Rode 'ollama serve' em outro terminal."
fi
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
