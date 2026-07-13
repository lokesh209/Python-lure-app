"""One-click HiPerGator authentication.

Runs ``ssh <alias> "echo ok"`` through a pseudo-TTY so we can:

1. Auto-supply the GatorLink password (stored in the OS keychain via ``keyring``).
2. Auto-pick "Duo Push" when prompted.
3. Stream status updates to the UI (so the user sees "Approve on your phone…"
   instead of being dropped into a terminal).

If the ControlMaster socket from a previous auth is still warm, this returns
within a few hundred ms with status="ok" and never touches Duo.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import AsyncIterator, Optional
from pathlib import Path

import keyring
import asyncssh

from ..core.config import hipergator_settings as hpg

KEYRING_SERVICE = "python-lure-app:hipergator"

_PROMPT_PASSWORD = re.compile(r"[Pp]assword:\s*$")
_PROMPT_DUO_OPTION = re.compile(r"Passcode or option \(1-\d\):\s*$")
_DUO_BANNER = re.compile(r"Duo two-factor login")


@dataclass
class AuthEvent:
    kind: str  # "info" | "duo" | "ok" | "error"
    message: str


def _fallback_path() -> Path:
    from ..core.config import _user_config_dir
    return _user_config_dir() / ".hpg_auth"

def get_stored_password() -> Optional[str]:
    try:
        pwd = keyring.get_password(KEYRING_SERVICE, hpg.ssh_alias)
        if pwd: return pwd
    except Exception:
        pass
    
    try:
        if _fallback_path().exists():
            return _fallback_path().read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return None

def store_password(password: str) -> None:
    try:
        p = _fallback_path()
        p.write_text(password, encoding="utf-8")
        p.chmod(0o600)
    except OSError:
        pass
    
    try:
        keyring.set_password(KEYRING_SERVICE, hpg.ssh_alias, password)
    except Exception:
        pass

def clear_password() -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, hpg.ssh_alias)
    except Exception:
        pass
    try:
        _fallback_path().unlink(missing_ok=True)
    except OSError:
        pass


async def quick_status() -> dict:
    """Cheap check: is the connection already established in the pool?"""
    from ..core.ssh_pool import pool
    conn = await pool.get_connection()
    if conn is not None:
        return {"status": "ok", "message": "Authenticated"}
    return {"status": "expired", "message": "Session expired — click Authenticate"}


class LureSSHClient(asyncssh.SSHClient):
    def __init__(self, pwd: str, q: asyncio.Queue[AuthEvent]):
        self.pwd = pwd
        self.q = q

    def kbdint_auth_requested(self) -> str:
        return ""  # Trigger custom kbdint_challenge_received

    def password_auth_requested(self) -> str:
        return self.pwd

    def connection_made(self, conn: asyncssh.SSHClientConnection) -> None:
        self.q.put_nowait(AuthEvent("info", "Connected to HiPerGator..."))

    def auth_completed(self) -> None:
        self.q.put_nowait(AuthEvent("ok", "Authenticated. Session is warm."))

    def kbdint_challenge_received(self, name: str, instructions: str, lang: str, prompts: list) -> list[str]:
        responses = []
        for prompt, _ in prompts:
            if "Password" in prompt:
                self.q.put_nowait(AuthEvent("info", "Sending password..."))
                responses.append(self.pwd)
            elif "Passcode or option" in prompt:
                self.q.put_nowait(AuthEvent("duo", "Approve the Duo push on your phone..."))
                responses.append("1")
            else:
                responses.append("")
        return responses

    def connection_lost(self, exc: Exception | None) -> None:
        if exc:
            self.q.put_nowait(AuthEvent("error", f"Connection lost: {exc}"))


async def authenticate(password: Optional[str] = None) -> AsyncIterator[AuthEvent]:
    """Connect using asyncssh, yield events to the UI, and store the connection in the pool."""
    import asyncssh
    from ..core.ssh_pool import pool

    pwd = password or get_stored_password()
    q: asyncio.Queue[AuthEvent | None] = asyncio.Queue()

    if not pwd:
        yield AuthEvent("error", "HiPerGator requires a password, but none was provided.")
        return

    yield AuthEvent("info", f"Connecting to {hpg.ssh_alias}…")

    async def _connect():
        try:
            # We must use the resolved host from config or ssh_alias.
            # asyncssh will parse ~/.ssh/config.
            options = asyncssh.SSHClientConnectionOptions(
                client_keys=None,
                preferred_auth=('keyboard-interactive', 'password')
            )
            
            def client_factory():
                return LureSSHClient(pwd, q)

            host = hpg.ssh_alias
            username = None
            if "@" in host:
                username, host = host.split("@", 1)

            conn, _ = await asyncssh.create_connection(
                client_factory,
                host,
                username=username,
                options=options
            )
            
            if password:
                store_password(password)
                
            await pool.set_connection(conn)
            q.put_nowait(None)  # Signal completion
        except asyncssh.Error as e:
            q.put_nowait(AuthEvent("error", f"SSH Error: {e}"))
            q.put_nowait(None)
        except Exception as e:
            q.put_nowait(AuthEvent("error", f"Error: {e}"))
            q.put_nowait(None)

    task = asyncio.create_task(_connect())

    while True:
        event = await q.get()
        if event is None:
            break
        yield event

    await task
