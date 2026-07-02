import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _user_config_dir() -> Path:
    """Per-user config dir that persists across .app updates.

    macOS:   ~/Library/Application Support/Python Lure/
    Linux:   ~/.config/python-lure/
    Windows: %APPDATA%/Python Lure/
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Python Lure"
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        return Path(base) / "Python Lure" if base else Path.home() / "Python Lure"
    return Path.home() / ".config" / "python-lure"


_USER_ENV = _user_config_dir() / ".env"
# Load order: user env (if it exists) wins over the dev-tree .env.
_ENV_FILES = (".env", str(_USER_ENV)) if _USER_ENV.exists() else (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_prefix="LURE_",
        extra="ignore",
    )

    data_root: Path = Path.home() / "PythonLureData"

    def model_post_init(self, _ctx) -> None:
        # Allow ~ in env values (e.g. LURE_DATA_ROOT=~/PythonLureData).
        self.data_root = self.data_root.expanduser()
    db_path: Path = Path("./lure.db")
    host: str = "127.0.0.1"
    port: int = 8000
    conf_threshold: float = 0.05
    detector: str = "mock"

    species_list: list[str] = [
        "python",
        "snake",
        "mammal",
        "human",
        "reptile",
        "bird",
    ]


class HiPerGatorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_prefix="HIPERGATOR_",
        extra="ignore",
    )

    ssh_alias: str = "hpg"
    remote_base: str = "/blue/ramccleery/makinenilokesh/lure_runs"
    conda_env: str = "/blue/ramccleery/makinenilokesh/envs/megadetector"
    account: str = "ramccleery"
    qos: str = "ramccleery"
    partition: str = "gpu"
    gres: str = "gpu:1"
    cpus: int = 4
    mem: str = "8gb"
    time: str = "24:00:00"
    email: str = ""
    poll_sec: int = 30
    keep_remote: bool = False
    #: Stop polling after this many hours (very long MegaDetector runs).
    max_poll_hours: float = 120.0
    #: If ``sacct`` stays empty this long after the job left ``squeue``, probe for output JSON.
    sacct_stale_sec: float = 600.0


settings = Settings()
hipergator_settings = HiPerGatorSettings()


def reload_settings() -> None:
    """Re-read .env files and update the singletons in place.

    Called after the user edits values via PATCH /api/settings so other
    modules (which imported the singletons at startup) immediately see the
    new values.
    """
    global _ENV_FILES
    _ENV_FILES = (".env", str(_USER_ENV)) if _USER_ENV.exists() else (".env",)

    new_s = Settings()
    new_h = HiPerGatorSettings()
    # Replace the contents of the existing instances so import-time bindings
    # (``from .config import settings``) keep working without reimport.
    settings.__dict__.update(new_s.__dict__)
    hipergator_settings.__dict__.update(new_h.__dict__)


def user_env_path() -> Path:
    """Where editable runtime config lives — created on first save."""
    return _USER_ENV
