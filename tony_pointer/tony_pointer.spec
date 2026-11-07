# -*- mode: python ; coding: utf-8 -*-
# Tony Pointer PyInstaller Specification File

import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect MediaPipe data files
mediapipe_datas = collect_data_files('mediapipe')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=mediapipe_datas + [
        ('settings.py', '.'),
        ('filters.py', '.'),
        ('mouse.py', '.'),
        ('tracker.py', '.'),
        ('gestures.py', '.'),
        ('camera.py', '.'),
        ('overlay.py', '.'),
        ('ui.py', '.'),
        ('keyboard_layout.py', '.'),
        ('keyboard_out.py', '.'),
        ('keyboard_ui.py', '.'),
        ('finger_taps.py', '.'),
        ('mode_manager.py', '.'),
    ],
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TonyPointer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # False for clean desktop app without black CMD window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,  # Set to True if you wish to control elevated installer/game windows
)
