from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..core.config import settings
from ..core.db import get_session
from ..core.ws import ws_manager
from ..models import Detection, Image, Project, ProjectStage
from ..services import csv_export
from ..services.exif import read_datetime as exif_datetime
from ..services.folder_naming import FolderNameError, build_folder_name, parse_folder_name
from ..services.ingest import copy_with_verify, list_source_images
from ..services.md_json import parse_md_json

router = APIRouter(prefix="/api/projects", tags=["projects"])


class IngestRequest(BaseModel):
    source: str = Field(..., description="Absolute path to SD-card source folder")
    date: str
    location: str
    site: str
    treatment: str
    interval: str
    is_sentinel: bool = False


class FolderInspect(BaseModel):
    path: str


class FolderInspectOut(BaseModel):
    exists: bool
    is_dir: bool
    name: str
    image_count: int
    parsed: Optional[dict]
    suggestion_reason: Optional[str] = None
    parent_parsed: Optional[dict] = None
    parent_name: Optional[str] = None
    suggested_path: Optional[str] = None
    conflict_project_id: Optional[int] = None
    conflict_project_folder: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    folder: str
    date: str
    location: str
    site: str
    treatment: str
    interval: str
    stage: ProjectStage
    is_sentinel: bool
    image_count: int
    detection_count: int
    flagged_count: int
    reviewed_count: int
    created_at: datetime
    detected_at: Optional[datetime]
    completed_at: Optional[datetime]

    @classmethod
    def from_db(cls, p: Project) -> "ProjectOut":
        return cls(**p.model_dump())


class ProjectPatch(BaseModel):
    censor_start: Optional[str] = None
    censor_end: Optional[str] = None
    censor_reason: Optional[str] = None
    other_notes: Optional[str] = None
    stage: Optional[ProjectStage] = None


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")
    return project


def _count_images(root: Path, deadline: float) -> tuple[int, bool]:
    """Walk ``root`` counting JPGs, abandoning the scan if we exceed deadline.

    Uses ``os.scandir`` directly so we don't pay for ``Path.is_file()``'s extra
    object construction on every entry — important on slow USB drives.
    Returns ``(count, hit_limit)``.
    """
    import os
    import time
    img_exts = (".jpg", ".jpeg")
    count = 0
    stack = [str(root)]
    while stack:
        if time.monotonic() > deadline:
            return count, True
        d = stack.pop()
        try:
            it = os.scandir(d)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue
        with it as entries:
            for e in entries:
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        if e.name.lower().endswith(img_exts):
                            count += 1
                except OSError:
                    pass
                if count >= 100_000:
                    return count, True
    return count, False


@router.post("/inspect-folder", response_model=FolderInspectOut)
async def inspect_folder(
    req: FolderInspect,
    session: Session = Depends(get_session),
) -> FolderInspectOut:
    """Validate a picked folder, count images, try to auto-parse the name.

    Smart enough that picking the inner ``100RECNX/`` folder still finds the
    parent project name (``09-03_RG_1_HM_1``) and pre-fills correctly. Also
    flags duplicate-folder collisions before the user kicks off a copy.
    """
    import asyncio
    import time

    p = Path(req.path).expanduser()
    try:
        if not p.exists():
            return FolderInspectOut(
                exists=False, is_dir=False, name=p.name,
                image_count=0, parsed=None,
                suggestion_reason="Folder does not exist or is unreadable.",
            )
        if not p.is_dir():
            return FolderInspectOut(
                exists=True, is_dir=False, name=p.name,
                image_count=0, parsed=None,
                suggestion_reason="That path is a file, not a folder.",
            )
    except PermissionError:
        return FolderInspectOut(
            exists=False, is_dir=False, name=p.name,
            image_count=0, parsed=None,
            suggestion_reason=(
                "macOS denied access. Open System Settings -> "
                "Privacy & Security -> Files and Folders and grant "
                "'Python Lure' access to the disk this folder lives on."
            ),
        )

    # Generous-but-bounded: an 8000-image folder on slow USB takes ~10 s;
    # we'd rather wait once than show "approximate".
    deadline = time.monotonic() + 20.0
    try:
        count, hit_limit = await asyncio.wait_for(
            asyncio.to_thread(_count_images, p, deadline),
            timeout=22.0,
        )
    except asyncio.TimeoutError:
        count, hit_limit = 0, True

    parsed = parse_folder_name(p.name)

    # If the picked folder is a Reconyx-style child (100RECNX, DCIM, Backups)
    # look one level up for the lab-convention parent and use that.
    parent_parsed: Optional[dict] = None
    parent_name: Optional[str] = None
    suggested_path: Optional[str] = None
    if parsed is None and p.parent != p:
        parent_parsed = parse_folder_name(p.parent.name)
        if parent_parsed is not None:
            parent_name = p.parent.name
            suggested_path = str(p.parent)

    # Detect "this project already exists" so we can offer a Open-existing
    # button instead of failing on ingest.
    effective_name: Optional[str] = None
    if parsed is not None:
        effective_name = p.name
    elif parent_parsed is not None:
        effective_name = parent_name
    conflict_project_id: Optional[int] = None
    conflict_folder: Optional[str] = None
    if effective_name:
        existing = session.exec(
            select(Project).where(Project.folder == effective_name)
        ).first()
        if existing:
            conflict_project_id = existing.id
            conflict_folder = existing.folder

    reason: Optional[str] = None
    if parsed is None and parent_parsed is None:
        reason = (
            f"Folder name '{p.name}' doesn't match the convention "
            "MM-DD_<location>_<site>_<treatment>_<interval>. "
            "Fill the fields manually."
        )
    elif parsed is None and parent_parsed is not None:
        reason = f"Auto-filled from the parent folder '{parent_name}'."
    if hit_limit and not reason:
        reason = "Lots of images — count is approximate."

    return FolderInspectOut(
        exists=True, is_dir=True, name=p.name,
        image_count=count,
        parsed=parsed,
        parent_parsed=parent_parsed,
        parent_name=parent_name,
        suggested_path=suggested_path,
        conflict_project_id=conflict_project_id,
        conflict_project_folder=conflict_folder,
        suggestion_reason=reason,
    )


def _stage_dir(stage: ProjectStage, is_sentinel: bool) -> Path:
    if is_sentinel:
        base = settings.data_root / "SentinelData"
    else:
        base = settings.data_root
    sub = {
        ProjectStage.needs_megadetector: "Needs_MegaDetector",
        ProjectStage.needs_id: "Needs_ID",
        ProjectStage.done_id: "Done_ID_without_CSV",
        ProjectStage.archived: "Done_ID",
    }[stage]
    return base / sub


def project_dir(project: Project) -> Path:
    return _stage_dir(project.stage, project.is_sentinel) / project.folder


def maybe_advance_to_done(session: Session, project: Project) -> bool:
    """Advance ``needs_id`` -> ``done_id`` if every flagged image is reviewed.

    Idempotent and safe to call from any read or write path. Returns True if
    the stage moved.
    """
    if project.stage != ProjectStage.needs_id:
        return False
    if project.flagged_count <= 0:
        return False
    if project.reviewed_count < project.flagged_count:
        return False
    try:
        _move_project_dir(project, ProjectStage.done_id)
    except Exception:  # noqa: BLE001
        # Don't let an FS hiccup block the DB-level state change.
        pass
    project.stage = ProjectStage.done_id
    project.completed_at = datetime.utcnow()
    session.add(project)
    session.commit()
    return True


def _move_project_dir(project: Project, new_stage: ProjectStage) -> Path:
    import shutil
    src = project_dir(project)
    dst = _stage_dir(new_stage, project.is_sentinel) / project.folder
    if src == dst:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        if dst.exists():
            raise HTTPException(409, f"Destination already exists: {dst}")
        shutil.move(str(src), str(dst))
    return dst


@router.get("/detect-running", response_model=dict)
def detect_running_ids() -> dict:
    """Which projects currently have a MegaDetector job in flight (server-side).

    Used by the dashboard to show a spinner even when the user isn't on the
    project detail page.
    """
    from . import detect as detect_mod
    return {"project_ids": list(detect_mod._running)}


@router.get("", response_model=list[ProjectOut])
def list_projects(
    session: Session = Depends(get_session),
    stage: Optional[ProjectStage] = None,
):
    # Self-heal: any project that finished review while we weren't watching
    # gets advanced before we filter / return.
    for p in session.exec(select(Project).where(Project.stage == ProjectStage.needs_id)):
        maybe_advance_to_done(session, p)

    query = select(Project).order_by(Project.created_at.desc())
    if stage is not None:
        query = query.where(Project.stage == stage)
    return [ProjectOut.from_db(p) for p in session.exec(query)]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    maybe_advance_to_done(session, project)
    session.refresh(project)
    return ProjectOut.from_db(project)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    patch: ProjectPatch,
    session: Session = Depends(get_session),
):
    project = _project_or_404(session, project_id)
    data = patch.model_dump(exclude_none=True)
    new_stage = data.pop("stage", None)
    for k, v in data.items():
        setattr(project, k, v)
    if new_stage is not None and new_stage != project.stage:
        _move_project_dir(project, new_stage)
        project.stage = new_stage
        if new_stage == ProjectStage.done_id:
            project.completed_at = datetime.utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return ProjectOut.from_db(project)


@router.delete("/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    
    existing_images = list(session.exec(select(Image).where(Image.project_id == project_id)))
    if existing_images:
        ids = [i.id for i in existing_images if i.id]
        if ids:
            for i in range(0, len(ids), 500):
                chunk = ids[i:i+500]
                for d in session.exec(select(Detection).where(Detection.image_id.in_(chunk))):
                    session.delete(d)
        for img in existing_images:
            session.delete(img)
            
    p_dir = project_dir(project)
    if p_dir.exists():
        import shutil
        shutil.rmtree(p_dir, ignore_errors=True)
        
    session.delete(project)
    session.commit()
    
    return {"ok": True}


@router.post("/ingest", response_model=ProjectOut)
async def ingest_project(
    req: IngestRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    try:
        folder = build_folder_name(
            date=req.date,
            location=req.location,
            site=req.site,
            treatment=req.treatment,
            interval=req.interval,
        )
    except FolderNameError as e:
        raise HTTPException(422, str(e))

    src = Path(req.source).expanduser()
    if not src.exists() or not src.is_dir():
        raise HTTPException(422, f"Source folder not found: {src}")

    existing = session.exec(select(Project).where(Project.folder == folder)).first()
    if existing:
        raise HTTPException(
            409,
            {
                "code": "project_exists",
                "message": f"Project '{folder}' already exists",
                "project_id": existing.id,
                "project_folder": existing.folder,
            },
        )

    project = Project(
        folder=folder,
        date=folder.split("_")[0],
        location=req.location,
        site=req.site,
        treatment=req.treatment,
        interval=req.interval,
        is_sentinel=req.is_sentinel,
        stage=ProjectStage.needs_megadetector,
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    dest = project_dir(project)
    dest.mkdir(parents=True, exist_ok=True)

    images = list_source_images(src)
    if not images:
        raise HTTPException(422, f"No JPG images found under {src}")

    project.image_count = len(images)
    session.add(project)
    session.commit()
    session.refresh(project)

    channel = f"project:{project.id}:ingest"

    async def _do_ingest():
        async def on_progress(i: int, total: int, name: str) -> None:
            await ws_manager.broadcast(channel, {
                "type": "ingest",
                "i": i, "total": total, "current": name,
            })

        results = await copy_with_verify(images, src, dest, on_progress)

        failures = [r for r in results if not r.ok]
        if failures:
            await ws_manager.broadcast(channel, {
                "type": "ingest_error",
                "failed": [{"src": str(f.src), "error": f.error} for f in failures[:25]],
                "failed_count": len(failures),
            })

        from ..core.db import engine
        with Session(engine) as bg_session:
            bg_project = bg_session.get(Project, project.id)
            if bg_project:
                for r in results:
                    if not r.ok:
                        continue
                    rel = r.dst.relative_to(dest)
                    relative_path = rel.parent.as_posix() if rel.parent != Path() else ""
                    bg_session.add(Image(
                        project_id=bg_project.id,
                        file=rel.name,
                        relative_path=relative_path,
                        file_hash=r.hash,
                        datetime_taken=exif_datetime(r.dst),
                    ))
                bg_project.image_count = sum(1 for r in results if r.ok)
                bg_session.add(bg_project)
                bg_session.commit()

        await ws_manager.broadcast(channel, {
            "type": "ingest_done",
            "image_count": sum(1 for r in results if r.ok),
            "failed_count": len(failures),
        })

    background_tasks.add_task(_do_ingest)

    return ProjectOut.from_db(project)


def do_import_detections(
    project_id: int,
    json_path: Optional[str],
    session: Session,
) -> Project:
    """Read recognitionData.json from disk and persist detections.

    Used both as a route (POST /import-detections) and called directly
    from the detection background task once the detector finishes.
    """
    project = _project_or_404(session, project_id)
    base = project_dir(project)
    p = Path(json_path) if json_path else (base / "recognitionData.json")
    if not p.exists():
        raise HTTPException(404, f"recognitionData.json not found at {p}")

    parsed = parse_md_json(p)

    # Index existing images by their canonical "RELATIVEPATH/FILE" key.
    existing = list(session.exec(select(Image).where(Image.project_id == project_id)))
    by_key: dict[str, Image] = {}
    for img in existing:
        key = (f"{img.relative_path}/{img.file}".lstrip("/")
               if img.relative_path else img.file)
        by_key[key] = img

    # Wipe previous detections for this project before reimport.
    if existing:
        ids = [i.id for i in existing if i.id]
        if ids:
            for i in range(0, len(ids), 500):
                chunk = ids[i:i+500]
                for d in session.exec(select(Detection).where(Detection.image_id.in_(chunk))):
                    session.delete(d)

    detection_count = 0
    flagged_count = 0
    threshold = settings.conf_threshold

    for parsed_img in parsed.images:
        key = parsed_img.file.replace("\\", "/").lstrip("./")
        img = by_key.get(key)
        if img is None:
            rel_path, _, fname = key.rpartition("/")
            img = Image(
                project_id=project_id,
                file=fname or key,
                relative_path=rel_path,
            )
            session.add(img)
            session.commit()
            session.refresh(img)
            by_key[key] = img

        kept = [d for d in parsed_img.detections if d.conf >= threshold]
        img.has_detections = bool(kept)
        img.max_conf = max((d.conf for d in parsed_img.detections), default=0.0)
        img.flagged = bool(kept)
        if img.flagged:
            flagged_count += 1
        # Backfill EXIF datetime for projects ingested before this feature
        # (also handles the "Import existing project" path).
        if not img.datetime_taken:
            full = base / img.relative_path / img.file if img.relative_path \
                else base / img.file
            if full.exists():
                img.datetime_taken = exif_datetime(full)

        for d in parsed_img.detections:
            session.add(Detection(
                image_id=img.id,
                category=d.category,
                conf=d.conf,
                bbox_x=d.bbox[0], bbox_y=d.bbox[1],
                bbox_w=d.bbox[2], bbox_h=d.bbox[3],
            ))
            detection_count += 1
        session.add(img)

    project.detection_count = detection_count
    project.flagged_count = flagged_count
    project.detected_at = datetime.utcnow()
    if project.stage == ProjectStage.needs_megadetector:
        _move_project_dir(project, ProjectStage.needs_id)
        project.stage = ProjectStage.needs_id
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.post("/{project_id}/import-detections", response_model=ProjectOut)
def import_detections_route(
    project_id: int,
    json_path: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    return ProjectOut.from_db(do_import_detections(project_id, json_path, session))


def _maybe_archive_on_export(session: Session, project: Project) -> None:
    """Mark a fully-reviewed project as archived once its CSV is downloaded."""
    if project.stage == ProjectStage.done_id:
        try:
            _move_project_dir(project, ProjectStage.archived)
        except Exception:  # noqa: BLE001
            pass
        project.stage = ProjectStage.archived
        session.add(project)
        session.commit()


@router.get("/{project_id}/csv")
def download_per_folder_csv(project_id: int, session: Session = Depends(get_session)):
    from fastapi.responses import Response
    project = _project_or_404(session, project_id)
    maybe_advance_to_done(session, project)
    body = csv_export.per_folder_csv(session, project)

    # Persist the CSV inside the project folder before we (potentially) rename
    # it to ``Done_ID/`` — the lab convention is that ``Done_ID/`` always
    # contains the CSV, while ``Done_ID_without_CSV/`` does not. Write first,
    # then archive, so the rename moves the saved CSV along with the rest of
    # the deployment.
    filename = f"{project.folder}_ImageData.csv"
    try:
        out_path = project_dir(project) / filename
        out_path.write_text(body, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    _maybe_archive_on_export(session, project)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/master")
def download_master_csv(session: Session = Depends(get_session)):
    from fastapi.responses import Response
    projects = list(session.exec(select(Project)))
    body = csv_export.master_csv(session, projects)
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="ImageData_DBExport.csv"'
        },
    )
