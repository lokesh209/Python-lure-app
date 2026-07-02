"""Detector contract. Both the mock and the future HiPerGator client implement
this so the rest of the app is detector-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Protocol


ProgressCb = Callable[[str, float | None, str, str | None], Awaitable[None]]


@dataclass
class DetectionJob:
    project_id: int
    folder: str
    image_dir: Path
    output_json: Path


class Detector(Protocol):
    name: str

    async def run(self, job: DetectionJob, on_progress: ProgressCb) -> Path:
        """Run detection and return the path to the resulting JSON."""
        ...
