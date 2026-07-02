"""Read EXIF DateTimeOriginal from a JPG and normalise to the lab's CSV format.

The lab's existing per-folder CSVs and DBExport.py output use a space-separated
ISO-ish format: ``2025-08-27 20:12:00``. EXIF natively uses colons in the date
portion (``2025:08:27 20:12:00``), so we normalise.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage

# Standard EXIF tag IDs
_DATETIME_ORIGINAL = 36867
_DATETIME_DIGITIZED = 36868
_DATETIME = 306


def read_datetime(path: Path) -> str:
    """Return ``YYYY-MM-DD HH:MM:SS`` or empty string if not available.

    Tries DateTimeOriginal first (camera shot time), falls back to
    DateTimeDigitized then DateTime. Never raises — returns "" on any error.
    """
    try:
        with PILImage.open(path) as im:
            exif = im.getexif()
            if not exif:
                return ""
            for tag in (_DATETIME_ORIGINAL, _DATETIME_DIGITIZED, _DATETIME):
                v = exif.get(tag)
                if v:
                    return _normalise(str(v))
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _normalise(s: str) -> str:
    s = s.strip().rstrip("\x00")
    # EXIF date-time uses colons in the date part: "YYYY:MM:DD HH:MM:SS"
    if len(s) >= 10 and s[4] == ":" and s[7] == ":":
        s = s[:4] + "-" + s[5:7] + "-" + s[8:]
    return s
