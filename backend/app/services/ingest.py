"""SD-card ingest with hash-verified copy.

The lab's `Note on Data.txt` flagged silent MS-DOS copy errors. We hash every
source and destination file and surface mismatches loudly instead of swallowing
them.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

IMAGE_EXTS = {".jpg", ".jpeg", ".JPG", ".JPEG"}


@dataclass
class CopyResult:
    src: Path
    dst: Path
    hash: str
    ok: bool
    error: str = ""


def _hash_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def list_source_images(source: Path) -> list[Path]:
    """Find Reconyx-style image files in the source directory.

    Per the existing MegaDetector_run.py, the lab's cameras put images in
    folders containing 'RECNX' (e.g. 100RECNX/) so we mirror that shape but
    are tolerant of cards that just dump JPGs at the root.
    """
    if not source.exists():
        raise FileNotFoundError(source)

    images: list[Path] = []
    for root, _dirs, files in os.walk(source):
        for fname in files:
            ext = os.path.splitext(fname)[1]
            if ext in IMAGE_EXTS:
                images.append(Path(root) / fname)
    return sorted(images)


ProgressCb = Callable[[int, int, str], Awaitable[None]]


async def copy_with_verify(
    images: list[Path],
    source_root: Path,
    dest_root: Path,
    on_progress: ProgressCb | None = None,
) -> list[CopyResult]:
    """Copy each file then re-hash both ends to confirm bit-perfect transfer."""
    results: list[CopyResult] = []
    total = len(images)

    for i, src in enumerate(images, 1):
        try:
            rel = src.relative_to(source_root)
        except ValueError:
            rel = Path(src.name)

        # Preserve only the camera subfolder structure (e.g. 100RECNX/file.JPG)
        # instead of the full SD-card path.
        if len(rel.parts) > 2:
            rel = Path(*rel.parts[-2:])

        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.to_thread(shutil.copy2, src, dst)
            src_hash = await asyncio.to_thread(_hash_file, src)
            dst_hash = await asyncio.to_thread(_hash_file, dst)
            if src_hash != dst_hash:
                results.append(
                    CopyResult(
                        src=src, dst=dst, hash="", ok=False,
                        error="hash mismatch after copy",
                    )
                )
            else:
                results.append(
                    CopyResult(src=src, dst=dst, hash=src_hash, ok=True)
                )
        except Exception as e:  # noqa: BLE001
            results.append(
                CopyResult(src=src, dst=dst, hash="", ok=False, error=str(e))
            )

        if on_progress is not None:
            await on_progress(i, total, str(rel))

    return results
