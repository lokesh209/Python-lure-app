from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..core.db import engine, get_session
from ..core.ws import ws_manager
from ..detectors.base import DetectionJob
from ..models import Project
from pydantic import BaseModel
from .projects import do_import_detections, project_dir

router = APIRouter(prefix="/api/projects", tags=["detect"])


_running: set[int] = set()
_tasks: dict[int, asyncio.Task] = {}
_last_progress: dict[int, dict[str, Any]] = {}


def _snapshot_progress(
    project_id: int,
    stage: str,
    pct: float | None,
    msg: str,
    detector: str,
    jobid: str | None = None,
) -> None:
    """Remember last progress so HTTP polling works when WebSocket missed events."""
    _last_progress[project_id] = {
        "stage": stage,
        "pct": pct,
        "msg": msg,
        "detector": detector,
        "jobid": jobid,
        "ts": time.time(),
    }


def _import_detections_sync(project_id: int) -> None:
    """DB work after detector.run — must not run on the asyncio loop (blocks other jobs)."""
    with Session(engine) as inner:
        refreshed = inner.get(Project, project_id)
        if refreshed:
            refreshed.detected_at = datetime.utcnow()
            inner.add(refreshed)
            inner.commit()
        do_import_detections(project_id, None, inner)


@router.get("/{project_id}/detect-status")
def detect_status(project_id: int) -> dict:
    """Whether a MegaDetector job is currently in flight for this project."""
    return {"running": project_id in _running}


@router.get("/{project_id}/detect-progress")
def detect_progress(project_id: int) -> dict[str, Any]:
    """Latest detection stage for UI polling."""
    snap = _last_progress.get(project_id)
    base: dict[str, Any] = {"running": project_id in _running}
    if not snap:
        return {
            **base,
            "stage": None,
            "pct": None,
            "msg": "",
            "detector": "",
            "ts": None,
        }
    return {**base, **snap}


class DetectRequest(BaseModel):
    detector: str | None = None
    hipergator_mem: str | None = None


@router.post("/{project_id}/detect")
async def start_detection(
    project_id: int,
    req: DetectRequest | None = None,
    session: Session = Depends(get_session),
):
    if req is None:
        req = DetectRequest()
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")
    if project.id in _running:
        raise HTTPException(409, "Detection already running for this project")

    _last_progress.pop(project.id, None)

    base = project_dir(project)
    output_json = base / "recognitionData.json"
    job = DetectionJob(
        project_id=project.id,
        folder=project.folder,
        image_dir=base,
        output_json=output_json,
    )
    from ..core.config import settings as app_settings
    detector_name = req.detector or app_settings.detector or "mock"
    detector_name = detector_name.lower()

    if detector_name == "local":
        from ..detectors.local import LocalDetector
        detector = LocalDetector()
    elif detector_name == "mock":
        from ..detectors.mock import MockDetector
        detector = MockDetector()
    else:
        from ..detectors.hipergator import HiPerGatorDetector
        detector = HiPerGatorDetector(mem=req.hipergator_mem)

    channel = f"project:{project.id}:detect"

    async def on_progress(stage: str, pct: float | None, msg: str, jobid: str | None = None) -> None:
        _snapshot_progress(project.id, stage, pct, msg, detector.name, jobid)
        await ws_manager.broadcast(channel, {
            "type": "detect", "stage": stage, "pct": pct, "msg": msg,
            "detector": detector.name, "jobid": jobid,
        })

    _running.add(project.id)

    async def runner() -> None:
        _snapshot_progress(
            project.id, "starting", 0.02, "Starting detection job…", detector.name
        )
        try:
            if not job.output_json.exists():
                await detector.run(job, on_progress)
            else:
                await on_progress("done", 1.0, "Found existing recognitionData.json; skipping detection.", None)
                
            await asyncio.to_thread(_import_detections_sync, project.id)
            _snapshot_progress(
                project.id, "imported", 1.0, "Detections imported", detector.name
            )
            await ws_manager.broadcast(channel, {
                "type": "detect", "stage": "imported", "pct": 1.0,
                "msg": "Detections imported", "detector": detector.name,
            })
        except asyncio.CancelledError:
            _snapshot_progress(project.id, "cancelled", None, "Job cancelled by user", detector.name)
            await ws_manager.broadcast(channel, {
                "type": "detect", "stage": "cancelled", "pct": None,
                "msg": "Job cancelled by user", "detector": detector.name,
            })
        except Exception as e:  # noqa: BLE001
            _snapshot_progress(project.id, "error", None, str(e), detector.name)
            await ws_manager.broadcast(channel, {
                "type": "detect", "stage": "error", "pct": None,
                "msg": str(e), "detector": detector.name,
            })
        finally:
            _running.discard(project.id)
            _tasks.pop(project.id, None)

    task = asyncio.create_task(runner())
    _tasks[project.id] = task
    return {"status": "started", "detector": detector.name, "channel": channel}


@router.post("/{project_id}/detect-cancel")
async def cancel_detection(project_id: int):
    """Cancel the running job (local task and/or remote SLURM job)."""
    # 1. Cancel the local runner task (handles Local/Mock/HPG-polling)
    task = _tasks.get(project_id)
    if task and not task.done():
        task.cancel()
    
    # 2. If it's a HiPerGator job, also try to scancel the remote job
    snap = _last_progress.get(project_id)
    if snap and snap.get("jobid"):
        jobid = snap["jobid"]
        from ..core.config import hipergator_settings as hpg
        try:
            await asyncio.create_subprocess_exec(
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                hpg.ssh_alias, f"scancel {jobid}",
            )
        except Exception:
            pass # Best effort scancel
            
    _running.discard(project_id)
    return {"ok": True}
