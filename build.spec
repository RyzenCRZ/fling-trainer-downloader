# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — 风灵月影修改器搜索下载器"""

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('dependency/7z.exe', 'dependency'),
        ('dependency/7z.dll', 'dependency'),
        ('dependency/7-zip.dll', 'dependency'),
        ('dependency/7-zip32.dll', 'dependency'),
    ],
    datas=[
        ('game_dict.json', '.'),
        ('assets/app_icon.ico', 'assets'),
    ],
    hiddenimports=[
        'cloudscraper',
        'rapidfuzz',
        'rapidfuzz.fuzz',
        'rapidfuzz.process',
        'pypinyin',
        'pypinyin.style',
        'pypinyin.core',
        'zhon',
        'zhon.cedict',
        'PyQt5.sip',
        'dict_builder',
        'search',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Cheat Engine Loader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico',
)
