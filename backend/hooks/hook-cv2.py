"""
Custom hook to properly bundle cv2 with numpy 2.x support.
Overrides the contrib hook that ships with pyinstaller-hooks-contrib.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Collect all cv2 data + binaries
datas, binaries, hiddenimports = collect_all('cv2')

# Explicitly pull in numpy _core (numpy 2.x renamed from numpy.core)
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
datas += numpy_datas
binaries += numpy_binaries
hiddenimports += numpy_hiddenimports

# Ensure critical numpy submodules are available  
hiddenimports += [
    'numpy._core',
    'numpy._core._multiarray_umath',
    'numpy._core.multiarray',
    'numpy._core._exceptions',
    'numpy._core.numeric',
    'numpy._core._methods',
    'numpy._core.fromnumeric',
    'numpy._core._ufunc_config',
    'numpy.lib',
    'numpy.linalg',
]
