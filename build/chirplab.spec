# -*- mode: python ; coding: utf-8 -*-

# get this list of measurement types that need to be manually imported
# todo: clean this up. This is subject to weird import order problems and there is almost certainly a better way to do this with ast or just parsing the text of CLMeasurements __init__.py
import sys
sys.path.insert(0, '../src')
import CLProject
import CLGui
import CLAnalysis
import CLMeasurements
measurement_list = ['CLMeasurements.'+measurement for measurement in CLMeasurements.MEASUREMENT_TYPES]

from PyInstaller.utils.hooks import collect_submodules
#measurement_list = collect_submodules('CLMeasurements') # collect_submodules('CLMeasurements') doesn't actually find the measurements, use the ugly solution above for now
scipy_array_api_compat = collect_submodules('scipy._lib.array_api_compat.numpy.fft') # workaround for an issue when bundling in GitHub build action
hidden_imports = measurement_list + scipy_array_api_compat

datas = [
    ['../src/CLGui/icon.png', './CLGui'],
    ['../src/CLGui/splash.png', './CLGui'],
    ['../examples/new-project_response.wav', '.'],
]

a = Analysis(
    ['../src/chirplab.py'],
    pathex=['../src'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chirplab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    #console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../img/icon.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='chirplab',
)


# include files at the same level as the bundled executable
from distutils.dir_util import copy_tree
copy_tree('../examples', DISTPATH+'/chirplab/examples')