import asyncio
import logging
import asyncssh
from typing import Optional

logger = logging.getLogger(__name__)

class SSHPool:
    def __init__(self):
        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._lock = asyncio.Lock()

    async def get_connection(self) -> Optional[asyncssh.SSHClientConnection]:
        async with self._lock:
            return self._conn
            
    async def set_connection(self, conn: asyncssh.SSHClientConnection) -> None:
        async with self._lock:
            if self._conn:
                self._conn.close()
            self._conn = conn

    async def close(self) -> None:
        async with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

pool = SSHPool()
