"""Read/write the user's ``.env`` file safely.

We preserve comments and key order so the file stays human-readable for any
future hand-editing. Writes are atomic via os.replace.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_KV_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*(.*?)\s*$")


def read_env(path: Path) -> dict[str, str]:
    """Return key->value for every assignment in the file.

    Lines that are blank or start with ``#`` are skipped. Keys are uppercased.
    """
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _KV_RE.match(line)
        if m:
            out[m.group(1)] = _strip_quotes(m.group(2))
    return out


def _strip_quotes(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def _quote_if_needed(v: str) -> str:
    """Quote values that contain whitespace or shell-special characters."""
    if v == "" or any(c in v for c in " \t#'\""):
        escaped = v.replace('"', '\\"')
        return f'"{escaped}"'
    return v


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Apply ``updates`` to ``path``, preserving existing layout where possible.

    Keys present in ``updates`` overwrite the existing value (or get appended
    at the end). Keys with value ``None`` are removed.
    Empty-string values *are* written — the user explicitly cleared the field.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    seen: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        m = _KV_RE.match(line)
        if not m:
            new_lines.append(line)
            continue
        key = m.group(1)
        if key in updates:
            seen.add(key)
            value = updates[key]
            if value is None:
                continue  # delete
            new_lines.append(f"{key}={_quote_if_needed(value)}")
        else:
            new_lines.append(line)

    # Append any keys that weren't already in the file.
    appended = [k for k in updates if k not in seen and updates[k] is not None]
    if appended:
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        for k in appended:
            new_lines.append(f"{k}={_quote_if_needed(updates[k])}")

    body = "\n".join(new_lines)
    if not body.endswith("\n"):
        body += "\n"

    # Atomic write so a crash mid-update doesn't corrupt the config.
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
