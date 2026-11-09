# -*- mode: python ; coding: utf-8 -*-
# Pointer V PyInstaller Specification File
# Builds onedir bundle in dist/PointerV/

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect MediaPipe model and resource files
mediapipe_datas = collect_data_files('mediapipe')

# Local assets (fonts, icons, images, models, sounds)
spec_dir = os.path.abspath(SPECPATH)
assets_dir = os.path.join(spec_dir, 'assets')
extra_datas = []
if os.path.exists(assets_dir):
    extra_datas.append((assets_dir, 'assets'))
    extra_datas.append((assets_dir, 'pointer_v/assets'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=mediapipe_datas + extra_datas,
    hiddenimports=[
        'keyboard',
        'psutil',
        'cv2',
        'numpy',
        'mediapipe',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'ui',
        'ui.widgets',
        'ui.main_window',
        'ui.tutorial_dialog',
        'ui.pages.dashboard_page',
        'ui.pages.camera_page',
        'ui.pages.gestures_page',
        'ui.pages.keyboard_page',
        'ui.pages.practice_page',
        'ui.pages.settings_page',
        'ui.pages.calibration_page',
        'ui.pages.about_page',
        'ui.pages.developer_page',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'scipy', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PointerV',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'icons', 'pointer_v.ico') if os.path.exists(os.path.join('assets', 'icons', 'pointer_v.ico')) else None,
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PointerV',
)

