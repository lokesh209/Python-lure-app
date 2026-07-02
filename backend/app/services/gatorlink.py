"""Auto-detect the user's GatorLink and derive HiPerGator paths from it.

Field workers shouldn't have to know about ``HIPERGATOR_REMOTE_BASE``,
``HIPERGATOR_CONDA_ENV``, etc. — they just type their GatorLink once and we
fill the rest.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


_SSH_HOST_BLOCK = re.compile(
    r"Host\s+([^\n]+?)\n((?:[ \t]+[^\n]+\n?)*)", re.IGNORECASE
)
_USER_LINE = re.compile(r"^\s*User\s+(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


def detect_from_ssh_config(alias: str = "hpg") -> Optional[str]:
    """Return the User= value for ``alias`` in ``~/.ssh/config``, if any."""
    cfg = Path.home() / ".ssh" / "config"
    if not cfg.exists():
        return None
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for m in _SSH_HOST_BLOCK.finditer(text):
        hosts = m.group(1).split()
        if alias in hosts or any(h == alias for h in hosts):
            user_match = _USER_LINE.search(m.group(2))
            if user_match:
                return user_match.group(1).strip()
    return None


def derive_paths(
    gatorlink: str,
    *,
    blue_dir: str = "/blue/ramccleery",
) -> dict[str, str]:
    """Return all HiPerGator path/email values for a given GatorLink."""
    g = gatorlink.strip().lower()
    return {
        "HIPERGATOR_REMOTE_BASE": f"{blue_dir}/{g}/lure_runs",
        "HIPERGATOR_CONDA_ENV": f"{blue_dir}/makinenilokesh/envs/megadetector",
        "HIPERGATOR_EMAIL": f"{g}@ufl.edu",
    }


_PLACEHOLDER_RE = re.compile(r"<\s*gatorlink\s*>", re.IGNORECASE)


def looks_unconfigured(value: Optional[str]) -> bool:
    """True if a config value is empty or still contains a ``<gatorlink>`` placeholder."""
    if not value:
        return True
    return bool(_PLACEHOLDER_RE.search(value))
