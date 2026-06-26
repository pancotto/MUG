# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


def asset_datas():
    entries = []
    assets_root = Path('assets')
    for path in sorted(assets_root.rglob('*')):
        if not path.is_file() or path.name == 'primata_cola_old.png':
            continue
        entries.append((str(path), str(path.parent)))
    return entries


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=asset_datas() + [
        ('VERSION', '.'),
    ],
    hiddenimports=[],
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
    name='MUG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icons\\mug.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MUG',
)
