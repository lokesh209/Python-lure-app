#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Python Lure: starting backend on http://127.0.0.1:8000"

# First-run bootstrap
if [ ! -d backend/.venv ]; then
  echo "==> Creating Python venv..."
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --upgrade pip --quiet
  backend/.venv/bin/pip install -r backend/requirements.txt
fi
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi
if [ ! -d frontend/dist ]; then
  echo "==> Building frontend (one-time)..."
  (cd frontend && npm install --silent && npm run build)
fi

# Open browser shortly after
( sleep 2 && open "http://127.0.0.1:8000" >/dev/null 2>&1 ) &

cd backend
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
