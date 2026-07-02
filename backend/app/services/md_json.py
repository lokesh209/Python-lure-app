"""MegaDetector v1.4 result parser.

Schema (verified against real recognitionData.json files in Done_ID/):

{
  "info": {...},
  "detection_categories": {"1": "animal", "2": "person", "3": "vehicle"},
  "images": [
    {
      "file": "100RECNX/RCNX0052.JPG",
      "detections": [
        {"category": "1", "conf": 0.011, "bbox": [x, y, w, h]}
      ]
    }
  ]
}

`bbox` is normalized [x_min, y_min, width, height] in image-relative units.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


CATEGORY_NAMES = {"1": "animal", "2": "person", "3": "vehicle"}


@dataclass
class ParsedDetection:
    category: str
    category_name: str
    conf: float
    bbox: tuple[float, float, float, float]


@dataclass
class ParsedImage:
    file: str
    detections: list[ParsedDetection] = field(default_factory=list)

    @property
    def max_conf(self) -> float:
        return max((d.conf for d in self.detections), default=0.0)


@dataclass
class ParsedResults:
    images: list[ParsedImage]
    detection_categories: dict[str, str]
    info: dict


def parse_md_json(path: Path) -> ParsedResults:
    with open(path) as f:
        data = json.load(f)

    cats: dict[str, str] = data.get("detection_categories", CATEGORY_NAMES)
    info: dict = data.get("info", {})

    images: list[ParsedImage] = []
    for raw in data.get("images", []):
        det_objs: list[ParsedDetection] = []
        for d in raw.get("detections", []) or []:
            cat = str(d.get("category", ""))
            bbox = d.get("bbox", [0.0, 0.0, 0.0, 0.0])
            if len(bbox) != 4:
                continue
            det_objs.append(
                ParsedDetection(
                    category=cat,
                    category_name=cats.get(cat, cat),
                    conf=float(d.get("conf", 0.0)),
                    bbox=(float(bbox[0]), float(bbox[1]),
                          float(bbox[2]), float(bbox[3])),
                )
            )
        images.append(ParsedImage(file=raw.get("file", ""), detections=det_objs))

    return ParsedResults(images=images, detection_categories=cats, info=info)
