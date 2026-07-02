@echo off
setlocal
cd /d %~dp0..

echo ==^> Step 1/4: Bootstrapping Python venv (if needed)
if not exist backend\.venv (
  python -m venv backend\.venv
)
backend\.venv\Scripts\pip install --upgrade pip
backend\.venv\Scripts\pip install -r backend\requirements.txt
backend\.venv\Scripts\pip install pyinstaller==6.11.1
:: Force reinstall opencv-python-headless to ensure it's compatible with numpy 2.x
backend\.venv\Scripts\pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python
backend\.venv\Scripts\pip install --no-cache-dir opencv-python-headless==4.13.0.92

echo ==^> Patching cv2/__init__.py for PyInstaller frozen-bundle compatibility...
backend\.venv\Scripts\python -c "import sys, re, os; init_path = 'backend/.venv/Lib/site-packages/cv2/__init__.py'; content = open(init_path, 'r').read(); new_guard = '''    if hasattr(sys, 'OpenCV_LOADER'):\n        if getattr(sys, 'frozen', False):\n            import importlib.util as _ilu\n            _loader_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))\n            _so_candidates = [f for f in os.listdir(_loader_dir) if f.startswith('cv2') and ('.so' in f or f.endswith('.pyd'))]\n            if _so_candidates:\n                _so_path = os.path.join(_loader_dir, _so_candidates[0])\n                _spec = _ilu.spec_from_file_location('cv2', _so_path)\n                _native = _ilu.module_from_spec(_spec)\n                _old_cv2 = sys.modules.get('cv2')\n                sys.modules['cv2'] = _native\n                try:\n                    _spec.loader.exec_module(_native)\n                finally:\n                    if _old_cv2 is not None:\n                        sys.modules['cv2'] = _old_cv2\n                _g = globals()\n                for _k, _v in _native.__dict__.items():\n                    if _k not in ('__file__', '__loader__', '__spec__', '__name__', '__package__', '__doc__'):\n                        _g.setdefault(_k, _v)\n            return\n        raise ImportError('ERROR: recursion is detected during loading of \"cv2\" binary extensions. Check OpenCV installation.')\n    sys.OpenCV_LOADER = True'''; pattern = r\"    if hasattr\(sys, 'OpenCV_LOADER'\):.*?    sys\.OpenCV_LOADER = True\"; content = re.sub(pattern, new_guard, content, flags=re.DOTALL); content = content.replace('    import numpy.core.multiarray\\n', '    try:\\n        import numpy._core.multiarray\\n    except ImportError:\\n        pass\\n    import numpy.core.multiarray\\n'); open(init_path, 'w').write(content)"
echo   Done.

echo ==^> Step 2/4: Building frontend
pushd frontend
call npm install --silent
call npm run build
popd

echo ==^> Step 3/4: Cleaning previous build
if exist backend\build rmdir /s /q backend\build
if exist backend\dist rmdir /s /q backend\dist
if exist dist rmdir /s /q dist
mkdir dist

echo ==^> Step 4/4: Running PyInstaller
pushd backend
call .venv\Scripts\pyinstaller --noconfirm PythonLure.spec
popd

if exist backend\dist (
  xcopy /E /I /Y backend\dist\* dist\
)

echo.
echo =================================================================
echo   Build complete.
echo.
if exist "dist\PythonLure" (
  echo   Find your compiled executable in dist\PythonLure\PythonLure.exe
)
