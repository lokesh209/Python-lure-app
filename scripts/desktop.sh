#!/usr/bin/env bash
# Launch the Python Lure desktop window without PyInstaller.
# Faster than build_app.sh — for dev iteration before bundling.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d backend/.venv ]; then
  echo "==> First-run setup (Python venv + deps + frontend build)"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --upgrade pip --quiet
  backend/.venv/bin/pip install -r backend/requirements.txt
fi
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi
if [ ! -d frontend/dist ]; then
  (cd frontend && npm install --silent && npm run build)
fi

cd backend
exec .venv/bin/python desktop.py
