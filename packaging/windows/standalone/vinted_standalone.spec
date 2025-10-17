# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Ensure CustomTkinter assets and submodules are bundled.
datas = collect_data_files("customtkinter")
hiddenimports = collect_submodules("customtkinter") + ["PIL._tkinter_finder"]

# Application entry point executed as a module in development.
entry_point = os.path.join(os.path.dirname(__file__), "..", "..", "..", "app", "main.py")
entry_point = os.path.normpath(entry_point)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


a = Analysis(
    [entry_point],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="VintedAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    upx=True,
    upx_exclude=[],
    name="VintedAssistant",
)
