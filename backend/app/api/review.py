from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from PIL import Image as PILImage
from pydantic import BaseModel
from sqlmodel import Session, func, select

from ..core.config import settings
from ..core.db import get_session
from ..models import Detection, Image, Project, ImageTag
from .projects import maybe_advance_to_done, project_dir

router = APIRouter(prefix="/api/projects", tags=["review"])


class DetectionOut(BaseModel):
    category: str
    category_name: str
    conf: float
    bbox: list[float]

class ImageTagOut(BaseModel):
    id: Optional[int] = None
    species: str
    count: int

class ImageOut(BaseModel):
    id: int
    file: str
    relative_path: str
    flagged: bool
    reviewed: bool
    species: str
    count: int
    delete_flag: bool
    max_conf: float
    width: int
    height: int
    detections: list[DetectionOut] = []
    tags: list[ImageTagOut] = []


class TagPatch(BaseModel):
    species: Optional[str] = None
    count: Optional[int] = None
    delete_flag: Optional[bool] = None
    reviewed: Optional[bool] = None
    tags: Optional[list[ImageTagOut]] = None


_CATEGORY_NAMES = {"1": "animal", "2": "person", "3": "vehicle"}


def _to_out(img: Image, dets: list[Detection], tags: list[ImageTag]) -> ImageOut:
    return ImageOut(
        id=img.id,
        file=img.file,
        relative_path=img.relative_path,
        flagged=img.flagged,
        reviewed=img.reviewed,
        species=img.species or "",
        count=img.count or 0,
        delete_flag=img.delete_flag,
        max_conf=img.max_conf,
        width=img.width,
        height=img.height,
        detections=[
            DetectionOut(
                category=d.category,
                category_name=_CATEGORY_NAMES.get(d.category, d.category),
                conf=d.conf,
                bbox=[d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h],
            )
            for d in dets
        ],
        tags=[
            ImageTagOut(id=t.id, species=t.species, count=t.count)
            for t in tags
        ]
    )


@router.get("/{project_id}/images", response_model=list[ImageOut])
def list_images(
    project_id: int,
    session: Session = Depends(get_session),
    flagged_only: bool = Query(True),
    only_unreviewed: bool = Query(False),
    sort_by: str = Query("id", pattern="^(id|max_conf|max_conf_desc)$"),
    limit: int = Query(2000, le=5000),
    offset: int = Query(0, ge=0),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")

    q = select(Image).where(Image.project_id == project_id)
    if flagged_only:
        q = q.where(Image.flagged == True)  # noqa: E712
    if only_unreviewed:
        q = q.where(Image.reviewed == False)  # noqa: E712
    if sort_by in ("max_conf_desc", "max_conf"):
        q = q.order_by(Image.max_conf.desc(), Image.id)
    else:
        q = q.order_by(Image.id)
    q = q.offset(offset).limit(limit)
    images = list(session.exec(q))
    if not images:
        return []

    ids = [i.id for i in images]
    dets = list(session.exec(select(Detection).where(Detection.image_id.in_(ids))))
    by_img: dict[int, list[Detection]] = {}
    for d in dets:
        by_img.setdefault(d.image_id, []).append(d)
        
    tags_rows = list(session.exec(select(ImageTag).where(ImageTag.image_id.in_(ids))))
    tags_by_img: dict[int, list[ImageTag]] = {}
    for t in tags_rows:
        tags_by_img.setdefault(t.image_id, []).append(t)

    return [_to_out(img, by_img.get(img.id, []), tags_by_img.get(img.id, [])) for img in images]


@router.get("/{project_id}/images/{image_id}/file")
def serve_image_file(
    project_id: int,
    image_id: int,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    img = session.get(Image, image_id)
    if not project or not img or img.project_id != project_id:
        raise HTTPException(404, "Image not found")

    base = project_dir(project)
    rel = Path(img.relative_path) / img.file if img.relative_path else Path(img.file)
    full = base / rel
    if not full.exists():
        raise HTTPException(404, f"File missing on disk: {full}")

    if not img.width or not img.height:
        try:
            with PILImage.open(full) as pim:
                img.width, img.height = pim.size
            session.add(img)
            session.commit()
        except Exception:  # noqa: BLE001
            pass

    return FileResponse(full, media_type="image/jpeg")


@router.patch("/{project_id}/images/{image_id}", response_model=ImageOut)
def update_image_tag(
    project_id: int,
    image_id: int,
    patch: TagPatch,
    session: Session = Depends(get_session),
):
    img = session.get(Image, image_id)
    if not img or img.project_id != project_id:
        raise HTTPException(404, "Image not found")
    data = patch.model_dump(exclude_none=True, exclude={"tags"})
    for k, v in data.items():
        setattr(img, k, v)
        
    if patch.tags is not None:
        # Delete existing tags
        existing_tags = session.exec(select(ImageTag).where(ImageTag.image_id == image_id)).all()
        for t in existing_tags:
            session.delete(t)
        # Add new tags
        for t_patch in patch.tags:
            new_tag = ImageTag(image_id=image_id, species=t_patch.species, count=t_patch.count)
            session.add(new_tag)

    session.add(img)
    session.commit()
    session.refresh(img)

    project = session.get(Project, project_id)
    if project:
        reviewed_count = session.exec(
            select(func.count(Image.id))
            .where(Image.project_id == project_id)
            .where(Image.reviewed == True)  # noqa: E712
        ).one()
        project.reviewed_count = int(reviewed_count or 0)
        session.add(project)
        session.commit()
        maybe_advance_to_done(session, project)

    dets = list(session.exec(select(Detection).where(Detection.image_id == image_id)))
    tags = list(session.exec(select(ImageTag).where(ImageTag.image_id == image_id)))
    return _to_out(img, dets, tags)
