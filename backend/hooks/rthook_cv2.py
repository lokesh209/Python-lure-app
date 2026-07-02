"""
Runtime hook — runs before any user code in the frozen app.
1. Pre-loads numpy C-extensions so cv2 finds them immediately.
2. Adds Contents/Resources to sys.path so packages like yolov5 that
   open their own __file__ at runtime can find their .py/.pyc files.
"""
import sys
import os

# ── 1. Ensure Resources/ is on sys.path (noarchive puts .pyc there) ──────────
if getattr(sys, 'frozen', False):
    # _MEIPASS is the temp extraction dir; for .app bundles, Resources is the
    # canonical location of noarchive .pyc files.
    resources = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))),
        "Resources",
    )
    if os.path.isdir(resources) and resources not in sys.path:
        sys.path.insert(0, resources)

# ── 2. Pre-load numpy C-extensions before cv2 needs them ─────────────────────
try:
    import numpy
    import numpy._core
    import numpy._core.multiarray
    import numpy._core._multiarray_umath
except Exception as _e:
    print(f"[rthook] numpy pre-load warning: {_e}")
