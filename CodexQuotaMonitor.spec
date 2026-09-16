# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


project_root = Path(SPECPATH)
src_dir = project_root / "src"
ffi_dll = Path(sys.executable).parent / "Library" / "bin" / "ffi.dll"
extra_binaries = [(str(ffi_dll), ".")] if ffi_dll.is_file() else []

a = Analysis(
    [str(src_dir / "main.py")],
    pathex=[str(src_dir)],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=["scanner", "windows_app"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CodexQuotaMonitor_v1.4",
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
    icon=str(project_root / "assets" / "CodexQuotaMonitor.ico"),
)
