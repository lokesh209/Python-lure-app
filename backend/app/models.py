from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ProjectStage(str, Enum):
    needs_megadetector = "needs_megadetector"
    needs_id = "needs_id"
    done_id = "done_id"
    archived = "archived"


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    folder: str = Field(unique=True, index=True)
    date: str
    location: str
    site: str
    treatment: str
    interval: str
    is_sentinel: bool = False
    stage: ProjectStage = Field(default=ProjectStage.needs_megadetector)
    censor_start: str = ""
    censor_end: str = ""
    censor_reason: str = ""
    other_notes: str = ""
    image_count: int = 0
    detection_count: int = 0
    flagged_count: int = 0
    reviewed_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    detected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Image(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    file: str
    relative_path: str
    datetime_taken: Optional[str] = None
    file_hash: str = ""
    width: int = 0
    height: int = 0
    has_detections: bool = False
    max_conf: float = 0.0
    flagged: bool = False
    species: str = ""
    count: int = 0
    delete_flag: bool = False
    reviewed: bool = False


class Detection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    image_id: int = Field(foreign_key="image.id", index=True)
    category: str
    conf: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float


class ImageTag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    image_id: int = Field(foreign_key="image.id", index=True)
    species: str
    count: int = 1
