# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for WebhookNt8Bridge receiver EXE (system-tray, no console).

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("pystray")
hiddenimports += ["tzdata", "PIL"]

a = Analysis(
    ["tray_app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("config.defaults.json", "."),
        ("assets/icon.ico", "assets"),
        ("assets/icon.png", "assets"),
    ],
    hiddenimports=hiddenimports,
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
    name="WebhookReceiver",
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
    icon="assets/icon.ico",
)
