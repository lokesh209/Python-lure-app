#!/usr/bin/env bash
# Build the Python Lure desktop app (.app on macOS, folder on Linux/Windows).
#
# Usage: ./scripts/build_app.sh
#
# After it finishes, drag dist/Python Lure.app to /Applications and double-click.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Step 1/4: Bootstrapping Python venv (if needed)"
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi
backend/.venv/bin/pip install --upgrade pip --quiet
backend/.venv/bin/pip install -r backend/requirements.txt --quiet
backend/.venv/bin/pip install pyinstaller==6.11.1 --quiet
# Force reinstall opencv-python-headless to ensure it's compatible with numpy 2.x
backend/.venv/bin/pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python --quiet 2>/dev/null || true
backend/.venv/bin/pip install --no-cache-dir opencv-python-headless==4.13.0.92 --quiet

echo "==> Patching cv2/__init__.py for PyInstaller frozen-bundle compatibility..."
backend/.venv/bin/python3 - << 'PYEOF'
import sys
init_path = "backend/.venv/lib/python3.12/site-packages/cv2/__init__.py"
with open(init_path, "r") as f:
    content = f.read()

# The patch we want - direct .so loader to avoid import system recursion
new_guard = """    if hasattr(sys, 'OpenCV_LOADER'):
        if getattr(sys, 'frozen', False):
            # PyInstaller frozen bundle: load the native .so directly.
            # We must use 'cv2' as the name so the native code's internal
            # checks pass, but we swap it in sys.modules to avoid conflict.
            import importlib.util as _ilu
            _loader_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
            _so_candidates = [
                f for f in os.listdir(_loader_dir)
                if f.startswith('cv2') and ('.so' in f or f.endswith('.pyd'))
            ]
            if _so_candidates:
                _so_path = os.path.join(_loader_dir, _so_candidates[0])
                _spec = _ilu.spec_from_file_location('cv2', _so_path)
                _native = _ilu.module_from_spec(_spec)
                _old_cv2 = sys.modules.get('cv2')
                sys.modules['cv2'] = _native
                try:
                    _spec.loader.exec_module(_native)
                finally:
                    if _old_cv2 is not None:
                        sys.modules['cv2'] = _old_cv2
                
                # Copy native symbols to the package module
                _g = globals()
                for _k, _v in _native.__dict__.items():
                    if _k not in ('__file__', '__loader__', '__spec__', '__name__', '__package__', '__doc__'):
                        _g.setdefault(_k, _v)
            return
        print(sys.path)
        raise ImportError('ERROR: recursion is detected during loading of "cv2" binary extensions. Check OpenCV installation.')
    sys.OpenCV_LOADER = True"""

# Match either the original guard OR any previous version of our patch
import re
# Replace everything between the start of the if-hasattr block and sys.OpenCV_LOADER = True
pattern = r"    if hasattr\(sys, 'OpenCV_LOADER'\):.*?    sys\.OpenCV_LOADER = True"
if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, new_guard, content, flags=re.DOTALL)
    print("  Patched recursion guard OK")
else:
    print("  WARNING: could not find guard pattern - skipping")

content = content.replace(
    "    import numpy.core.multiarray\n",
    "    try:\n        import numpy._core.multiarray\n    except ImportError:\n        pass\n    import numpy.core.multiarray\n"
)
with open(init_path, "w") as f:
    f.write(content)
print("  Done.")
PYEOF

echo "==> Step 2/4: Building frontend"
(cd frontend && npm install --silent && npm run build)

echo "==> Step 3/4: Cleaning previous build"
rm -rf backend/build backend/dist dist
mkdir -p dist

echo "==> Step 4/4: Running PyInstaller"
(cd backend && .venv/bin/pyinstaller --noconfirm PythonLure.spec)

# PyInstaller dumps into backend/dist; move artifacts up to ./dist for clarity.
if [ -d backend/dist ]; then
  mv backend/dist/* dist/
fi

echo
echo "================================================================="
echo "  Build complete."
echo
if [ -d "dist/Python Lure.app" ]; then
  echo "  -> dist/Python Lure.app"
  echo "  Drag it to /Applications and double-click to launch."
elif [ -d "dist/PythonLure" ]; then
  echo "  -> dist/PythonLure/"
  echo "  Run: ./dist/PythonLure/PythonLure"
fi
echo "================================================================="
