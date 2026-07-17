"""CSV exports matching the lab's existing scripts.

Two outputs:

1. **Per-folder CSV** -> mirrors the manual Timelapse export shape:
   `Folder, File, RelativePath, DateTime, Species, Count`

2. **Master CSV** -> mirrors `DBExport.py` so `ActivityViz.Rmd` keeps working:
   adds DeleteFlag, censor fields, detection summary stats per category, hash.
"""
from __future__ import annotations

import csv
from io import StringIO
from typing import Iterable

from sqlmodel import Session, select

from ..models import Detection, Image, Project, ImageTag


PER_FOLDER_COLS = ["Folder", "File", "RelativePath", "DateTime", "Species", "Count"]

MASTER_COLS = [
    "Id", "File", "RelativePath", "DateTime", "DeleteFlag", "Species", "Count",
    "Folder",
    "censorStart", "censorEnd", "censorReason", "otherNotes",
    "num_detections", "conf_avg", "conf_min", "conf_max",
    "count_animal", "count_person", "count_vehicle",
    "file_hash",
]


def _images_for(session: Session, project: Project) -> list[Image]:
    return list(
        session.exec(
            select(Image).where(Image.project_id == project.id).order_by(Image.id)
        )
    )


def _detections_for(session: Session, image_ids: list[int]) -> dict[int, list[Detection]]:
    if not image_ids:
        return {}
    out: dict[int, list[Detection]] = {}
    for i in range(0, len(image_ids), 500):
        chunk = image_ids[i:i+500]
        rows = session.exec(select(Detection).where(Detection.image_id.in_(chunk))).all()
        for d in rows:
            out.setdefault(d.image_id, []).append(d)
    return out


def _tags_for(session: Session, image_ids: list[int]) -> dict[int, list[ImageTag]]:
    if not image_ids:
        return {}
    out: dict[int, list[ImageTag]] = {}
    for i in range(0, len(image_ids), 500):
        chunk = image_ids[i:i+500]
        rows = session.exec(select(ImageTag).where(ImageTag.image_id.in_(chunk))).all()
        for t in rows:
            out.setdefault(t.image_id, []).append(t)
    return out


def _format_tags(img: Image, tags: list[ImageTag]) -> tuple[str, str]:
    if tags:
        species_str = ", ".join(t.species for t in tags)
        count_str = ", ".join(str(t.count) for t in tags)
        return species_str, count_str
    # Fallback to old single columns for backwards compatibility
    return img.species or "", str(img.count) if img.count else "0"


def per_folder_csv(session: Session, project: Project) -> str:
    images = _images_for(session, project)
    tags_by_img = _tags_for(session, [i.id for i in images if i.id])
    
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=PER_FOLDER_COLS)
    writer.writeheader()
    for img in images:
        species_str, count_str = _format_tags(img, tags_by_img.get(img.id or -1, []))
        writer.writerow({
            "Folder": project.folder,
            "File": img.file,
            "RelativePath": img.relative_path,
            "DateTime": img.datetime_taken or "",
            "Species": species_str,
            "Count": count_str,
        })
    return buf.getvalue()


def _detection_summary(dets: list[Detection]) -> dict:
    if not dets:
        return {
            "num_detections": 0,
            "conf_avg": "", "conf_min": "", "conf_max": "",
            "count_animal": 0, "count_person": 0, "count_vehicle": 0,
        }
    confs = [d.conf for d in dets]
    cat_to_name = {"1": "animal", "2": "person", "3": "vehicle"}
    counts = {"animal": 0, "person": 0, "vehicle": 0}
    for d in dets:
        name = cat_to_name.get(d.category)
        if name:
            counts[name] += 1
    return {
        "num_detections": len(dets),
        "conf_avg": sum(confs) / len(confs),
        "conf_min": min(confs),
        "conf_max": max(confs),
        "count_animal": counts["animal"],
        "count_person": counts["person"],
        "count_vehicle": counts["vehicle"],
    }


def master_csv(session: Session, projects: Iterable[Project]) -> str:
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=MASTER_COLS)
    writer.writeheader()

    for project in projects:
        images = _images_for(session, project)
        image_ids = [i.id for i in images if i.id]
        dets_by_img = _detections_for(session, image_ids)
        tags_by_img = _tags_for(session, image_ids)
        
        for img in images:
            summary = _detection_summary(dets_by_img.get(img.id or -1, []))
            species_str, count_str = _format_tags(img, tags_by_img.get(img.id or -1, []))
            
            writer.writerow({
                "Id": img.id,
                "File": img.file,
                "RelativePath": img.relative_path,
                "DateTime": img.datetime_taken or "",
                "DeleteFlag": "true" if img.delete_flag else "false",
                "Species": species_str,
                "Count": count_str,
                "Folder": project.folder,
                "censorStart": project.censor_start,
                "censorEnd": project.censor_end,
                "censorReason": project.censor_reason,
                "otherNotes": project.other_notes,
                "file_hash": img.file_hash,
                **summary,
            })
    return buf.getvalue()

