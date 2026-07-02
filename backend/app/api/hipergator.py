"""HiPerGator status + one-click authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..services import hpg_auth

router = APIRouter(prefix="/api/hipergator", tags=["hipergator"])


class StatusOut(BaseModel):
    status: str  # "ok" | "expired" | "no_config"
    message: str
    has_saved_password: bool


@router.get("/status", response_model=StatusOut)
async def status() -> StatusOut:
    s = await hpg_auth.quick_status()
    return StatusOut(
        status=s["status"],
        message=s["message"],
        has_saved_password=hpg_auth.get_stored_password() is not None,
    )


class ForgetOut(BaseModel):
    ok: bool


@router.post("/forget", response_model=ForgetOut)
def forget() -> ForgetOut:
    hpg_auth.clear_password()
    return ForgetOut(ok=True)


class DisconnectOut(BaseModel):
    ok: bool


@router.post("/disconnect", response_model=DisconnectOut)
async def disconnect() -> DisconnectOut:
    import asyncio
    from ..core.config import hipergator_settings as hpg
    proc = await asyncio.create_subprocess_exec(
        "ssh", "-O", "exit", hpg.ssh_alias,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    return DisconnectOut(ok=True)


@router.websocket("/auth")
async def auth_ws(ws: WebSocket) -> None:
    """Streaming auth.

    Client connects, sends ``{"password": "..."}`` (or ``{}`` to use the
    keychain entry), and receives a sequence of
    ``{"kind": "info"|"duo"|"ok"|"error", "message": "..."}`` events.
    """
    await ws.accept()
    try:
        first = await ws.receive_json()
    except WebSocketDisconnect:
        return

    password = first.get("password") or None

    try:
        async for evt in hpg_auth.authenticate(password=password):
            try:
                await ws.send_json({"kind": evt.kind, "message": evt.message})
            except Exception:  # noqa: BLE001
                break
            if evt.kind in ("ok", "error"):
                break
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
