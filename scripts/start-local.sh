#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

if [[ ! -f ".env" ]]; then
  echo "Missing .env. Copy .env.example to .env and fill in the required values."
  exit 1
fi

for command in python3 npm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command"
    exit 1
  fi
done

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "Missing .venv. Run:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

if [[ ! -d "web/node_modules" ]]; then
  echo "Missing web/node_modules. Run:"
  echo "  cd web && npm ci"
  exit 1
fi

set -a
source ".env"
set +a

required_env=(
  "OPENAI_API_KEY"
  "NEO4J_URI"
  "NEO4J_USERNAME"
  "NEO4J_PASSWORD"
  "AWS_REGION"
)

missing_env=()
for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing_env+=("$name")
  fi
done

if (( ${#missing_env[@]} > 0 )); then
  echo "Missing required env vars in .env:"
  printf '  - %s\n' "${missing_env[@]}"
  exit 1
fi

if [[ -n "${PROMPT_S3_BUCKET:-}" ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "PROMPT_S3_BUCKET is set, so AWS CLI is required for S3 access."
    exit 1
  fi

  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "PROMPT_S3_BUCKET is set, but AWS credentials are not configured."
    echo "Run 'aws configure', set AWS_PROFILE, or unset PROMPT_S3_BUCKET to use local file storage."
    exit 1
  fi
fi

cleanup() {
  local exit_code=$?
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

source ".venv/bin/activate"

echo "Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
python3 -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
  > >(sed 's/^/[backend] /') 2>&1 &
BACKEND_PID=$!

echo "Starting frontend on http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd web
  NEXT_PUBLIC_API_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}" \
    npm run dev -- --hostname "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) > >(sed 's/^/[frontend] /') 2>&1 &
FRONTEND_PID=$!

echo
echo "Prompt Similarity Service is booting."
echo "Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "Backend:  http://${BACKEND_HOST}:${BACKEND_PORT}"
echo
echo "Press Ctrl+C to stop both processes."

wait -n "$BACKEND_PID" "$FRONTEND_PID"
