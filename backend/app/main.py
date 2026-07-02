from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import detect, hipergator, projects, review, settings as settings_api, ws
from .core.config import settings
from .core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    try:
        Path(settings.data_root).expanduser().mkdir(parents=True, exist_ok=True)
    except (PermissionError, FileNotFoundError, OSError) as e:
        # Don't crash the app if the data root can't be created (e.g. external
        # drive not mounted). The user can fix it in Settings or replug the
        # drive without restarting.
        print(
            f"[warn] Could not access data_root '{settings.data_root}': {e}. "
            "Server will start but ingest/detect will fail until this is fixed."
        )
    init_db()
    yield


app = FastAPI(
    title="Python Lure App",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(detect.router)
app.include_router(review.router)
app.include_router(settings_api.router)
app.include_router(hipergator.router)
app.include_router(ws.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "data_root": str(settings.data_root),
        "detector": settings.detector,
    }


# Serve built React bundle in production (frontend/dist exists after `npm run build`).
# Search both the dev tree layout and the PyInstaller bundle layout so this
# works whether you launch via `uvicorn`, `python desktop.py`, or the .app.
def _find_frontend_dist() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        # PyInstaller --onedir: data files live under sys._MEIPASS.
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass:
            candidates.append(meipass / "frontend" / "dist")
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / "frontend" / "dist")  # dev tree
    candidates.append(here.parents[1] / "frontend" / "dist")  # alt layout
    for c in candidates:
        if c.exists():
            return c
    return None


_dist = _find_frontend_dist()
if _dist is not None:
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
