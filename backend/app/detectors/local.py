import asyncio
import json
import urllib.request
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlmodel import Session, select
import logging

logger = logging.getLogger(__name__)

from ..core.config import settings
from .base import Detector, DetectionJob, ProgressCb


class LocalDetector(Detector):
    name = "local"

    def __init__(self):
        super().__init__()
        self.weights_url = "https://github.com/microsoft/CameraTraps/releases/download/v5.0/md_v5a.0.0.pt"
        self.weights_path = settings.data_root / "models" / "md_v5a.0.0.pt"

    async def _download_weights_if_missing(self, on_progress: ProgressCb) -> None:
        if self.weights_path.exists():
            return

        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        
        await on_progress("downloading", 0.0, "Downloading MegaDetector weights (100MB) for local inference...", None)

        def download():
            try:
                urllib.request.urlretrieve(self.weights_url, self.weights_path)
            except Exception as e:
                logger.error(f"Failed to download weights: {e}")
                if self.weights_path.exists():
                    self.weights_path.unlink()
                raise

        await asyncio.to_thread(download)

    async def run(self, job: DetectionJob, on_progress: ProgressCb) -> Path:
        """Run MegaDetector locally using ultralytics YOLOv5 on mps/cpu."""
        try:
            # 1. Download weights
            await self._download_weights_if_missing(on_progress)

            # 2. Load model
            await on_progress("running", 0.05, "Loading MegaDetector model...", None)

            def _walk_images(root: Path) -> list[Path]:
                import os
                out: list[Path] = []
                for r, _dirs, files in os.walk(root):
                    for f in files:
                        if f.lower().endswith((".jpg", ".jpeg")):
                            out.append(Path(r) / f)
                return sorted(out)

            images = await asyncio.to_thread(_walk_images, job.image_dir)
            img_paths = [str(img) for img in images]
            import threading
            stop_event = threading.Event()
            loop = asyncio.get_running_loop()

            def load_and_infer():
                try:
                    import yolov5
                except ImportError as e:
                    raise RuntimeError(f"yolov5 package is not installed. Cannot run local detector: {e}")

                import torch
                device = "mps" if torch.backends.mps.is_available() else "cpu"

                # yolov5.load handles YOLOv5-format .pt files (MegaDetector v5a)
                # PyTorch 2.6+ defaults weights_only=True which blocks loading these checkpoints.
                _orig_torch_load = torch.load
                torch.load = lambda *a, **kw: _orig_torch_load(*a, **{**kw, 'weights_only': False})
                try:
                    model = yolov5.load(str(self.weights_path))
                finally:
                    torch.load = _orig_torch_load

                model.conf = settings.conf_threshold
                model.iou = 0.45
                model.to(device)

                # Run inference
                out_images = []

                total = len(img_paths)
                for i, img_path in enumerate(img_paths):
                    if stop_event.is_set():
                        logger.info("Local detector received stop event; exiting loop.")
                        return None

                    if i % 10 == 0 or i == total - 1:
                        progress = 0.05 + (0.90 * (i / max(total, 1)))
                        asyncio.run_coroutine_threadsafe(
                            on_progress("running", progress, f"Detecting {i}/{total} ({device})", None),
                            loop
                        )

                    results = model(img_path, size=1280)
                    pred = results.pred[0]  # tensor (N,6): x1,y1,x2,y2,conf,cls

                    img_width = results.ims[0].shape[1]
                    img_height = results.ims[0].shape[0]

                    detections = []
                    for det in pred:
                        x1, y1, x2, y2, conf, cls = det.tolist()
                        category = str(int(cls) + 1)  # 0:animal→"1", 1:person→"2", 2:vehicle→"3"

                        nx = x1 / img_width
                        ny = y1 / img_height
                        nw = (x2 - x1) / img_width
                        nh = (y2 - y1) / img_height

                        detections.append({
                            "category": category,
                            "conf": round(conf, 3),
                            "bbox": [round(nx, 4), round(ny, 4), round(nw, 4), round(nh, 4)]
                        })

                    rel_path = Path(img_path).relative_to(job.image_dir).as_posix()
                    out_images.append({
                        "file": rel_path,
                        "detections": detections
                    })

                results_json = {
                    "info": {
                        "format_version": "1.4",
                        "detector": "local",
                    },
                    "detection_categories": {"1": "animal", "2": "person", "3": "vehicle"},
                    "images": out_images,
                }

                json_path = job.output_json
                json_path.parent.mkdir(parents=True, exist_ok=True)
                with open(json_path, "w") as f:
                    json.dump(results_json, f, indent=2)

                return json_path

            try:
                json_path = await asyncio.to_thread(load_and_infer)
                if json_path is None: # Means we were cancelled
                    raise asyncio.CancelledError()
            except asyncio.CancelledError:
                stop_event.set()
                raise

            await on_progress("done", 1.0, "Inference complete!", None)
            return json_path

        except Exception as e:
            logger.exception("Local detection failed")
            raise
