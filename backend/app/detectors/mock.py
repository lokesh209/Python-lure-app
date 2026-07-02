"""Mock detector. Generates a plausible recognitionData.json without any real
inference, so the rest of the app can be developed end-to-end before we have
HiPerGator credentials.

Behavior:
- Walks the project image directory.
- Assigns a small random number of detections to ~30% of images.
- Bbox/conf values look like real MegaDetector v1.4 output.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path

from .base import DetectionJob, ProgressCb


class MockDetector:
    name = "mock"

    async def run(self, job: DetectionJob, on_progress: ProgressCb) -> Path:
        await on_progress("starting", 0.0, "Mock detector warming up", None)
        await asyncio.sleep(0.3)

        def _walk_images(root: Path) -> list[Path]:
            out: list[Path] = []
            for r, _dirs, files in os.walk(root):
                for f in files:
                    if f.lower().endswith((".jpg", ".jpeg")):
                        out.append(Path(r) / f)
            return sorted(out)

        images = await asyncio.to_thread(_walk_images, job.image_dir)

        await on_progress("running", 0.05, f"Found {len(images)} images", None)

        rng = random.Random(job.folder)
        out_images = []
        for i, img_path in enumerate(images, 1):
            try:
                rel = img_path.relative_to(job.image_dir)
            except ValueError:
                rel = Path(img_path.name)
            rel_str = rel.as_posix()

            detections = []
            if rng.random() < 0.3:
                for _ in range(rng.randint(1, 2)):
                    cat = rng.choices(["1", "2", "3"], weights=[8, 1, 1])[0]
                    detections.append({
                        "category": cat,
                        "conf": round(rng.uniform(0.01, 0.95), 4),
                        "bbox": [
                            round(rng.uniform(0.0, 0.7), 4),
                            round(rng.uniform(0.0, 0.7), 4),
                            round(rng.uniform(0.1, 0.3), 4),
                            round(rng.uniform(0.1, 0.3), 4),
                        ],
                    })

            out_images.append({"file": rel_str, "detections": detections})

            if i % 25 == 0 or i == len(images):
                pct = i / max(len(images), 1)
                await on_progress("running", pct, f"{i}/{len(images)} images", None)
                await asyncio.sleep(0.01)

        result = {
            "info": {
                "detection_completion_time": "",
                "format_version": "1.4",
                "detector": "mock",
                "detector_metadata": {
                    "megadetector_version": "mock",
                    "typical_detection_threshold": 0.2,
                    "conservative_detection_threshold": 0.1,
                },
            },
            "detection_categories": {"1": "animal", "2": "person", "3": "vehicle"},
            "images": out_images,
        }

        def _write_json(path: Path, payload: dict) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)

        await asyncio.to_thread(_write_json, job.output_json, result)

        await on_progress("done", 1.0, f"Wrote {job.output_json.name}", None)
        return job.output_json
