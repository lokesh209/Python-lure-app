#!/usr/bin/env bash
# Dev mode: backend on :8000 (no auto-mounted frontend), Vite on :5173 with proxy.
set -euo pipefail
cd "$(dirname "$0")/.."

trap 'kill 0' EXIT INT TERM

(cd backend && .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &
wait
