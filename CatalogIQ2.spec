# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('app', 'app')]
hiddenimports = ['wx', 'wx.lib.mixins.listctrl']
datas += collect_data_files('certifi')
hiddenimports += collect_submodules('wx')
hiddenimports += collect_submodules('wx.lib')
hiddenimports += collect_submodules('wx.adv')
hiddenimports += collect_submodules('wx.html')


a = Analysis(
    ['start_catalogiq.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['wx.lib.pubsub.core.datamsg', 'wx.lib.pubsub.core.kwargs'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CatalogIQ2',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CatalogIQ2',
)
