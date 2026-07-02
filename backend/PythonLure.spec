# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Python Lure desktop app.

Build with:

    cd backend
    .venv/bin/pyinstaller --noconfirm PythonLure.spec

Outputs ``dist/Python Lure.app`` (macOS) / ``dist/Python Lure/`` (Linux).
On Windows, run from a Windows shell with the same command.
"""
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent  # noqa: F821 — SPECPATH is set by PyInstaller
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
SBATCH = ROOT / "sbatch"

if not FRONTEND_DIST.exists():
    sys.exit(
        "frontend/dist not found — run `npm run build` in frontend/ first."
    )

datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
    (str(SBATCH), "sbatch"),
    (str(BACKEND / "app"), "app"),
]

# Picked up implicitly by hooks, but listed for safety.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.protocols",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "engineio.async_drivers.threading",
    "keyring.backends.macOS",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "pexpect",
    "ptyprocess",
]

# Collect numpy first - must be done before cv2 to ensure C-extensions are found
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
datas.extend(numpy_datas)

for pkg in ["ultralytics", "torch", "torchvision", "yolov5"]:
    c_datas, c_binaries, c_hiddenimports = collect_all(pkg)
    datas.extend(c_datas)
    hiddenimports.extend(c_hiddenimports)

hiddenimports.extend(numpy_hiddenimports)
hiddenimports.extend([
    # numpy 2.x renamed core module — must be explicit for PyInstaller
    'numpy._core',
    'numpy._core._multiarray_umath',
    'numpy._core.multiarray',
    'numpy._core._exceptions',
    'numpy._core.numeric',
    'numpy._core._methods',
    'numpy._core.fromnumeric',
    'numpy._core._ufunc_config',
])

a = Analysis(
    [str(BACKEND / "desktop.py")],
    pathex=[str(BACKEND)],
    binaries=numpy_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(BACKEND / "hooks")],
    runtime_hooks=[str(BACKEND / "hooks" / "rthook_cv2.py")],
    excludes=["tkinter"],
    noarchive=True,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PythonLure",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PythonLure",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Python Lure.app",
        icon=None,
        bundle_identifier="org.ufl.lure.python-lure",
        info_plist={
            "CFBundleName": "Python Lure",
            "CFBundleDisplayName": "Python Lure",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSDesktopFolderUsageDescription":
                "Python Lure needs to read camera-trap images you've copied to "
                "your Desktop.",
            "NSDocumentsFolderUsageDescription":
                "Python Lure needs to read camera-trap images stored in "
                "Documents.",
            "NSDownloadsFolderUsageDescription":
                "Python Lure needs to read camera-trap images stored in "
                "Downloads.",
            "NSRemovableVolumesUsageDescription":
                "Python Lure needs to read images directly from SD cards and "
                "USB drives.",
            "NSNetworkVolumesUsageDescription":
                "Python Lure needs to read images stored on network volumes.",
            "NSAppleEventsUsageDescription":
                "Python Lure uses AppleEvents to reveal files in Finder.",
        },
    )
