# -*- mode: python ; coding: utf-8 -*-
# Modo ONEDIR deliberadamente: validação e diagnóstico antes do ONEFILE.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'templates'), 'templates')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
              'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.Qt3DCore'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Epic7ShopBot', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False,
          uac_admin=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name='Epic7ShopBot')
