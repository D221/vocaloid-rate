# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/static', 'static'),
        ('app/templates', 'templates')
    ],
    hiddenimports=[
        'uvicorn.lifespan.on',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='vocaloid-rate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='vocaloid-rate',
)