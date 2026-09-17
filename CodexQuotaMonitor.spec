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
    # 这些模块经依赖图与运行期导入追踪确认不在任何被执行的导入路径上
    # （ssl/hashlib 由 http/ftplib/urllib 以 try/except 保护；unicodedata 仅在
    #  re 的 \N{...} 分支内惰性导入；decimal 一族仅被 statistics/fractions 使用）。
    excludes=[
        "ssl",
        "_ssl",
        "hashlib",
        "_hashlib",
        "unicodedata",
        "decimal",
        "_decimal",
        "_pydecimal",
        "statistics",
        "fractions",
        "numbers",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CodexQuotaMonitor_v1.4.1",
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
