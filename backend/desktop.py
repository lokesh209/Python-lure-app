"""Desktop entrypoint: starts FastAPI in-process and shows it in a native window.

Run directly during development:

    cd backend && .venv/bin/python desktop.py

Or bundled into a .app via PyInstaller:

    pyinstaller backend/PythonLure.spec
    open dist/Python\\ Lure.app

The native window uses the OS's built-in WebView (WKWebView on macOS,
WebView2 on Windows) so we don't ship Chromium.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from contextlib import closing
from pathlib import Path

# When packaged with PyInstaller, ``sys._MEIPASS`` points at the unpacked
# resources directory. We also need to make ``app.*`` importable when the
# script is launched from the bundle.
if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    sys.path.insert(0, str(BUNDLE_ROOT))
else:
    BUNDLE_ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(BUNDLE_ROOT))


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.settimeout(0.25)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(0.1)
    return False


def _start_server(port: int) -> threading.Thread:
    """Run uvicorn on a background thread."""
    import uvicorn  # imported here so PyInstaller picks it up
    from app.main import app  # noqa: F401  (forces module load before server)

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    def _run() -> None:
        server.run()

    t = threading.Thread(target=_run, daemon=True, name="lure-server")
    t.start()
    return t


class JsBridge:
    """Methods exposed to the in-window JS via ``window.pywebview.api``."""

    def reveal(self, path: str) -> bool:
        """Reveal a file or folder in Finder / Explorer / Files."""
        try:
            if sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", "-R", path])
            elif sys.platform.startswith("win"):
                import subprocess
                subprocess.Popen(["explorer", "/select,", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
            return True
        except Exception:  # noqa: BLE001
            return False

    def pick_folder(self, start: str | None = None) -> str | None:
        """Show the OS-native folder picker and return the chosen path."""
        import webview
        windows = webview.windows
        if not windows:
            return None
        directory = start or "/Volumes" if sys.platform == "darwin" else start or ""
        result = windows[0].create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=directory,
            allow_multiple=False,
        )
        if not result:
            return None
        # pywebview returns a tuple/list of paths.
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def save_file(self, content: str, default_filename: str) -> bool:
        """Show the OS-native save dialog and save the text content."""
        import webview
        windows = webview.windows
        if not windows:
            return False
        result = windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=default_filename,
        )
        if not result:
            return False
        path = result[0] if isinstance(result, (list, tuple)) else str(result)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False


def main() -> None:
    import webview

    # Run from a writable cwd. Use the per-user config dir so the SQLite db
    # and any cwd-relative artefacts don't end up trapped in the read-only
    # bundle.
    from app.core.config import _user_config_dir
    work_dir = _user_config_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(work_dir)

    port = _free_port()
    _start_server(port)

    if not _wait_for_server("127.0.0.1", port):
        print("backend failed to come up on 127.0.0.1:%d" % port, file=sys.stderr)
        sys.exit(1)

    url = f"http://127.0.0.1:{port}/"
    webview.create_window(
        title="Python Lure",
        url=url,
        width=1280,
        height=820,
        min_size=(960, 640),
        confirm_close=False,
        js_api=JsBridge(),
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
