"""Editable user-facing settings.

Reads/writes the user-config ``.env`` file (e.g. on macOS,
``~/Library/Application Support/Python Lure/.env``) and live-reloads the
in-memory singletons so the rest of the app sees changes immediately.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.config import (
    hipergator_settings as hpg_settings,
    reload_settings,
    settings as app_settings,
    user_env_path,
)
from ..services import config_writer, gatorlink as gatorlink_helper

router = APIRouter(prefix="/api/settings", tags=["settings"])


class HiPerGatorBlock(BaseModel):
    ssh_alias: str
    remote_base: str
    conda_env: str
    account: str
    qos: str
    partition: str
    gres: str
    mem: str
    email: str
    poll_sec: int


class SettingsOut(BaseModel):
    data_root: str
    detector: str
    conf_threshold: float
    species_list: list[str]
    config_path: str
    config_exists: bool

    gatorlink: Optional[str]
    is_configured: bool
    hipergator: HiPerGatorBlock


def _gatorlink_from_paths() -> Optional[str]:
    """Pull the GatorLink back out of the configured remote_base, if present."""
    parts = (hpg_settings.remote_base or "").rstrip("/").split("/")
    # Expected: /blue/ramccleery/<gatorlink>/lure_runs
    if len(parts) >= 4 and parts[-1] == "lure_runs":
        candidate = parts[-2]
        if candidate and not gatorlink_helper.looks_unconfigured(candidate):
            return candidate
    # Fall back to ssh-config detection if path is still placeholder.
    return gatorlink_helper.detect_from_ssh_config(hpg_settings.ssh_alias)


def _is_configured() -> bool:
    return not (
        gatorlink_helper.looks_unconfigured(hpg_settings.remote_base)
        or gatorlink_helper.looks_unconfigured(hpg_settings.conda_env)
    )


def _current_out() -> SettingsOut:
    p = user_env_path()
    return SettingsOut(
        data_root=str(app_settings.data_root),
        detector=app_settings.detector,
        conf_threshold=app_settings.conf_threshold,
        species_list=app_settings.species_list,
        config_path=str(p),
        config_exists=p.exists(),
        gatorlink=_gatorlink_from_paths(),
        is_configured=_is_configured(),
        hipergator=HiPerGatorBlock(
            ssh_alias=hpg_settings.ssh_alias,
            remote_base=hpg_settings.remote_base,
            conda_env=hpg_settings.conda_env,
            account=hpg_settings.account,
            qos=hpg_settings.qos,
            partition=hpg_settings.partition,
            gres=hpg_settings.gres,
            mem=hpg_settings.mem,
            email=hpg_settings.email,
            poll_sec=hpg_settings.poll_sec,
        ),
    )


@router.get("", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return _current_out()


class SettingsPatch(BaseModel):
    """Editable subset of settings.

    ``gatorlink`` is a convenience field: when set, the backend derives
    ``remote_base``, ``conda_env`` and ``email`` from it (overriding any
    values in the same patch). Field workers should typically only need to
    fill ``gatorlink`` + ``data_root``.
    """
    gatorlink: Optional[str] = None
    data_root: Optional[str] = None
    detector: Optional[str] = None
    conf_threshold: Optional[float] = None

    hipergator_ssh_alias: Optional[str] = None
    hipergator_remote_base: Optional[str] = None
    hipergator_conda_env: Optional[str] = None
    hipergator_account: Optional[str] = None
    hipergator_qos: Optional[str] = None
    hipergator_partition: Optional[str] = None
    hipergator_gres: Optional[str] = None
    hipergator_mem: Optional[str] = None
    hipergator_email: Optional[str] = None
    hipergator_poll_sec: Optional[int] = None


_PATCH_TO_ENV = {
    "data_root": "LURE_DATA_ROOT",
    "detector": "LURE_DETECTOR",
    "conf_threshold": "LURE_CONF_THRESHOLD",
    "hipergator_ssh_alias": "HIPERGATOR_SSH_ALIAS",
    "hipergator_remote_base": "HIPERGATOR_REMOTE_BASE",
    "hipergator_conda_env": "HIPERGATOR_CONDA_ENV",
    "hipergator_account": "HIPERGATOR_ACCOUNT",
    "hipergator_qos": "HIPERGATOR_QOS",
    "hipergator_partition": "HIPERGATOR_PARTITION",
    "hipergator_gres": "HIPERGATOR_GRES",
    "hipergator_mem": "HIPERGATOR_MEM",
    "hipergator_email": "HIPERGATOR_EMAIL",
    "hipergator_poll_sec": "HIPERGATOR_POLL_SEC",
}


@router.patch("", response_model=SettingsOut)
def patch_settings(patch: SettingsPatch) -> SettingsOut:
    updates: dict[str, str] = {}

    data = patch.model_dump(exclude_none=True)

    # Convenience field — wins over any explicit hipergator_* paths in the
    # same patch.
    g = data.pop("gatorlink", None)
    if g:
        derived = gatorlink_helper.derive_paths(g)
        updates.update(derived)

    for field, value in data.items():
        env_key = _PATCH_TO_ENV.get(field)
        if env_key:
            updates[env_key] = str(value)

    if not updates:
        return _current_out()

    p = user_env_path()
    try:
        config_writer.write_env(p, updates)
    except OSError as e:
        raise HTTPException(500, f"Could not write config: {e}")
    reload_settings()
    return _current_out()


_DEFAULT_USER_ENV = """\
# Python Lure user config — edited via the Settings page.
# You don't normally need to touch this file directly.
LURE_DATA_ROOT=~/PythonLureData
LURE_DETECTOR=hipergator
LURE_CONF_THRESHOLD=0.05
"""


class ConfigPathOut(BaseModel):
    path: str
    created: bool


@router.post("/open-config", response_model=ConfigPathOut)
def open_config() -> ConfigPathOut:
    """Ensure the user config dir + .env exists, return its path.

    Frontend can then ask the OS to reveal it in Finder/Explorer.
    """
    p = user_env_path()
    cfg_dir = p.parent
    try:
        cfg_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(500, f"Could not create config dir: {e}")
    created = False
    if not p.exists():
        p.write_text(_DEFAULT_USER_ENV, encoding="utf-8")
        created = True
        reload_settings()
    return ConfigPathOut(path=str(p), created=created)
