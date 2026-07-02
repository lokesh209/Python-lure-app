@echo off
setlocal
cd /d %~dp0..

if not exist backend\.venv (
  echo ==^> Creating Python venv...
  python -m venv backend\.venv
  backend\.venv\Scripts\pip install --upgrade pip
  backend\.venv\Scripts\pip install -r backend\requirements.txt
)
if not exist backend\.env (
  copy backend\.env.example backend\.env
)
if not exist frontend\dist (
  echo ==^> Building frontend (one-time)...
  pushd frontend
  call npm install
  call npm run build
  popd
)

start "" http://127.0.0.1:8000

cd backend
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
